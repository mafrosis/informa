import contextlib
import inspect
import logging
import os
import pathlib
from collections.abc import Callable

import arrow
import click
import yaml
from dataclasses_json import DataClassJsonMixin
from marshmallow.exceptions import ValidationError
from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from informa.exceptions import AppError
from informa.lib import (
    ConfigBase,
    InformaPlugin,
    StateBase,
    _load_config,
    _load_state,
    _write_state,
    pass_plugin_name,
)
from informa.lib.utils import now_aest, raise_alarm

click_pass_plugin = click.make_pass_decorator(InformaPlugin)


@pass_plugin_name
def load_run_persist(
    plugin_name: str, logger: logging.Logger | logging.LoggerAdapter, state_cls: type[StateBase], main_func: Callable
):
    _load_run_persist(plugin_name, logger, state_cls, main_func, sync=False)


def _load_run_persist(
    plugin_name: str,
    logger: logging.Logger | logging.LoggerAdapter,
    state_cls: type[StateBase],
    main_func: Callable,
    sync: bool,
):
    '''
    Load plugin state, run plugin main function via callback, persist state to disk.

    Dynamically inspects the parameter `main_func` to determine if it has a parameter derived from
    `ConfigBase`, and if so, loads a plugin's config into an instance of this `ConfigBase` class.

    Params:
        plugin_name:  Plugin module name, supplied by the @pass_plugin_name decorator
        logger:       Logger for the calling plugin
        state_cls:    Plugin state dataclass which is persisted between runs
        main_func:    Callback function to trigger plugin logic
        sync:         False if this function was invoked asynchronously from a Rocketry task
    '''
    try:
        # Reload config each time plugin runs
        state = _load_state(plugin_name, logger, state_cls)

        plugin_config_class: type[ConfigBase] | None = None

        # Introspect the passed main_func for a Config parameter
        for param in inspect.getfullargspec(main_func).annotations.values():
            if issubclass(param, ConfigBase):
                plugin_config_class = param

        logger.info('Running, last run: %s', state.last_run or 'Never')

        # Reload config each time plugin runs
        config = _load_config(plugin_name, plugin_config_class)

        # Ensure state directory exists
        state_dir = pathlib.Path(os.environ.get('STATE_DIR', './state'))
        state_dir.mkdir(exist_ok=True)

        # Change current working directory to the state directory
        with contextlib.chdir(state_dir):
            # Run plugin's decorated main function with or without config
            if config is not None:
                ret = main_func(state, config)
            else:
                ret = main_func(state)

        # Handle misbehaving plugins (when main does not return a value)
        if ret is None:
            logger.debug('WARN: Plugin %s did not return a value', plugin_name)
            ret = 1

        # Update common plugin state attributes
        state.last_run = now_aest()
        state.last_count = ret

        if sync is False and logger.getEffectiveLevel() != logging.DEBUG:
            # Publish state to MQTT when running async
            publish_plugin_run_to_mqtt(plugin_name, state)
            logger.debug('Published to informa/%s via MQTT', plugin_name)

        # Persist plugin metadata
        _write_state(plugin_name, state)
        logger.debug('Plugin returned %s. State persisted.', ret)

    except AppError as e:
        raise_alarm(logger, str(e), e)
    except ValidationError as e:
        raise_alarm(logger, 'State ValidationError, possible corruption', e)
    except Exception as e:  # noqa: BLE001
        raise_alarm(logger, f'Unhandled exception {e.__class__.__name__}', e)


def publish_plugin_run_to_mqtt(plugin_name: str, state: StateBase):
    'Write plugin\'s output to a MQTT topic'
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.connect('trevor', 1883)
    client.publish(f'informa/{plugin_name}/last_run', state.last_run.isoformat(), retain=True)
    client.publish(f'informa/{plugin_name}/last_count', state.last_count, retain=True)


@pass_plugin_name
def write_config(plugin_name: str, config: DataClassJsonMixin):
    '''
    Write a config file

    Params:
        plugin_name:  Plugin module name, provided by the @pass_plugin_name decorator
        config:       Plugin config to serialise into JSON
    '''
    with open(f'config/{plugin_name}.yaml', 'w', encoding='utf8') as f:
        f.write(yaml.dump(config.to_dict()))


@pass_plugin_name
def load_config(
    plugin_name: str,
    config_cls: type[ConfigBase],
) -> DataClassJsonMixin | None:
    '''
    Load plugin config

    Params:
        plugin_name:  Plugin module name, supplied by the @pass_plugin_name decorator
        cls:          Plugin's config class type
    '''
    return _load_config(plugin_name, config_cls)


@pass_plugin_name
def load_state(
    plugin_name: str, logger: logging.Logger | logging.LoggerAdapter, state_cls: type[StateBase]
) -> StateBase:
    '''
    Load or initialise plugin state

    Params:
        plugin_name:  Plugin module name, provided by the @pass_plugin_name decorator
        directory:    Directory path; either 'config' or 'state'
        cls:          Plugin's state class type
    '''
    return _load_state(plugin_name, logger, state_cls)


@pass_plugin_name
def write_state(plugin_name: str, state_obj: StateBase):
    '''
    Utility function to write state to a file

    Params:
        plugin_name:  Plugin module name, provided by the @pass_plugin_name decorator
        state_obj:    Plugin's state object
    '''
    _write_state(plugin_name, state_obj)


@click.command('last-run')
@click_pass_plugin
def plugin_last_run(plugin: InformaPlugin):
    'When was the last run?'
    state = _load_state(plugin.name, plugin.logger, plugin.state_cls)
    last_run = arrow.get(state.last_run).humanize() if state.last_run else 'Never'
    print(f'Last run: {last_run} (returned {state.last_count})')


@click.command('run')
@click_pass_plugin
def plugin_run_now(plugin: InformaPlugin):
    'Run the plugin now in the foreground'
    _load_run_persist(plugin.name, plugin.logger, plugin.state_cls, plugin.main_func, sync=True)
