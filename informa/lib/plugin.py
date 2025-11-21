import contextlib
import datetime
import decimal
import inspect
import io
import json
import logging
import os
import pathlib
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from types import ModuleType
from typing import Any, TypeVar, cast

import arrow
import click
import orjson
import requests
import yaml
from dataclasses_json import DataClassJsonMixin
from fastapi import APIRouter
from marshmallow.exceptions import ValidationError
from paho.mqtt import client as mqtt
from paho.mqtt import publish as mqtt_publish
from paho.mqtt.enums import CallbackAPIVersion
from pydantic import BaseModel

from informa.exceptions import AppError, PluginRequiresConfigError, StateJsonDecodeError
from informa.lib import ConfigBase, PluginAdapter, StateBase
from informa.lib.utils import now_aest, raise_alarm

F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class InformaTask:
    func: F
    condition: str


class CliResponse(BaseModel):
    output: str


@dataclass
class InformaPlugin:
    module: ModuleType
    tasks: list[InformaTask] = field(default_factory=list)
    enabled: bool | None = None
    api: APIRouter | None = None
    informa_hostname: str | None = None
    last_run: datetime.datetime | None = None
    last_count: int | None = None
    commands: dict[str, click.core.Command] | None = None

    def __post_init__(self):
        'Load plugin state on startup to populate last_run, last_count'
        if self.state_cls:
            state = self.load_state()
            self.last_run = state.last_run
            self.last_count = state.last_count

    @property
    def name(self):
        return self.module.__name__

    @cached_property
    def cli(self):
        for _, member in inspect.getmembers(self.module):
            if isinstance(member, click.core.Group):
                return member

    @cached_property
    def logger(self):
        def get_plugin_logger():
            'Return the class attribute which is an instance of lib.PluginAdapter'
            return next(iter([v for _, v in inspect.getmembers(self.module) if isinstance(v, PluginAdapter)]), None)

        return get_plugin_logger()

    @cached_property
    def state_cls(self):
        return self.get_class_attr(StateBase) or StateBase

    @cached_property
    def config_cls(self):
        return self.get_class_attr(ConfigBase)

    @cached_property
    def main_func(self):
        return self.module.main

    def get_class_attr(self, type_):
        'Return the class type defined in the plugin, which inherits from `type_`'
        clss = [
            v for _, v in inspect.getmembers(self.module, inspect.isclass) if issubclass(v, type_) and v is not type_
        ]
        return next(iter(clss), None)


    def wrap_cli(self, cli_command: click.core.Command):
        'Wrap CLI functions with dispatcher'
        def dispatch(**kwargs):
            try:
                # Handle pathlib objects before JSON serialization
                for k, v in kwargs.items():
                    if isinstance(v, pathlib.Path):
                        kwargs[k] = str(v)
                    else:
                        kwargs[k] = v

                # POST the CLI kwargs to Informa server
                resp = requests.post(
                    f'{self.informa_hostname}/cli/{self.name}/{cli_command.name}',
                    json=kwargs,
                    timeout=2,
                    verify=os.environ.get('CA_CERT'),
                )
                resp.raise_for_status()
                print(resp.json()['output'].strip())

            except requests.exceptions.JSONDecodeError as e:
                if not resp.text:
                    raise click.ClickException('Empty response from the server') from e
            except TypeError as e:
                raise click.ClickException(f'Plugin CLI commands must include InformaPlugin as their first parameter ({self.name}.{cli_command.name})') from e
            except requests.exceptions.ConnectionError as e:
                raise click.ClickException('It appears that Informa is currently down') from e
            except requests.RequestException as e:
                raise click.ClickException(str(e)) from e

        cli_command.callback = dispatch
        return cli_command


    def cli_handler(self, cli_command: click.core.Command):
        'Handle HTTP requests by an Informa client CLI (calls originate in function `wrap_cli`)'
        def inner(kwargs: dict) -> CliResponse:
            # Handle pathlib objects serialized in the JSON request body
            for p in cli_command.params:
                if isinstance(p.type, click.types.Path):
                    kwargs[p.name] = pathlib.Path(kwargs[p.name])

            # Capture stdout from the CLI function and send in HTTP response
            with contextlib.redirect_stdout(io.StringIO()) as f:
                cli_command.inner_callback(self, **kwargs)
            return CliResponse(output=f.getvalue())
        return inner


    def load_config(self) -> DataClassJsonMixin | None:
        'Load plugin config'
        if self.config_cls is None:
            return None

        try:
            config_dir = os.environ.get('CONFIG_DIR', './config')

            with open(f'{config_dir}/{self.name}.yaml', encoding='utf8') as f:
                data = yaml.load(f, Loader=yaml.Loader)  # noqa: S506
                if not data:
                    return None
        except FileNotFoundError as e:
            raise PluginRequiresConfigError(self.name) from e

        return cast(ConfigBase, self.config_cls.from_dict(data))

    def load_state(self) -> StateBase:
        'Load or initialise plugin state'
        try:
            state_dir = os.environ.get('STATE_DIR', './state')

            with open(f'{state_dir}/{self.name}.json', encoding='utf8') as f:
                data = orjson.loads(f.read())
                if not data:
                    raise StateJsonDecodeError

            # Inflate JSON into the State dataclass
            state = self.state_cls.from_dict(data)
            self.logger.debug('Loaded state for %s', self.name)

        except (FileNotFoundError, orjson.JSONDecodeError):
            self.logger.debug('Empty state initialised for %s', self.name)
            state = self.state_cls()

        return cast(StateBase, state)

    def write_state(self, state: StateBase):
        'Persist plugin state to the filesystem'
        if not os.path.exists('state'):
            os.mkdir('state')

        def default(obj):
            'Handler for types unknown to orjson'
            if isinstance(obj, decimal.Decimal):
                return str(obj)
            if isinstance(obj, set):
                return list(obj)
            raise TypeError

        state_dir = os.environ.get('STATE_DIR', './state')

        with open(f'{state_dir}/{self.name}.json', 'w', encoding='utf8') as f:
            f.write(orjson.dumps(state, default=default).decode())


    def setup_mqtt(self):
        'Publish an autodiscovery message for a HA sensor'
        mqtt_publish.single(
            f'homeassistant/sensor/informa/{self.name}_last_run/config',
            json.dumps({
                'name': f'Informa {self.name} Last Run',
                'unique_id': f'informa.plugins.{self.name}.last_run',
                'state_topic': f'informa/informa.plugins.{self.name}/last_run',
                'device': {'identifiers': ['informa'], 'manufacturer': 'mafro'},
            }),
            hostname='trevor',
            retain=True,
        )

        mqtt_publish.single(
            f'homeassistant/sensor/informa/{self.name}_last_count/config',
            json.dumps({
                'name': f'Informa {self.name} Last Count',
                'unique_id': f'informa.plugins.{self.name}.last_count',
                'state_topic': f'informa/informa.plugins.{self.name}/last_count',
                'device': {'identifiers': ['informa'], 'manufacturer': 'mafro'},
            }),
            hostname='trevor',
            retain=True,
        )


    def execute(self, sync: bool = False):
        '''
        Load plugin state, run plugin main function via callback, persist state to disk.

        Dynamically inspects the parameter `main_func` to determine if it has a parameter derived from
        `ConfigBase`, and if so, loads a plugin's config into an instance of this `ConfigBase` class.

        Params:
            sync:  False if this function was invoked asynchronously from a Rocketry task
        '''
        try:
            state = self.load_state()

            self.logger.info('Running, last run: %s', state.last_run or 'Never')

            # Reload config each time plugin runs
            config = self.load_config()

            # Ensure state directory exists
            state_dir = pathlib.Path(os.environ.get('STATE_DIR', './state'))
            state_dir.mkdir(exist_ok=True)

            # Change current working directory to the state directory
            with contextlib.chdir(state_dir):
                # Run plugin's decorated main function with or without config
                if config is not None:
                    ret = self.main_func(state, config)
                else:
                    ret = self.main_func(state)

            # Handle misbehaving plugins (when main does not return a value)
            if ret is None:
                self.logger.debug('WARN: Plugin %s did not return a value', self.name)
                ret = 1

            # Update common plugin state attributes
            state.last_run = now_aest()
            state.last_count = ret

            if sync is False and self.logger.getEffectiveLevel() != logging.DEBUG:
                # Publish state to MQTT when running async
                publish_plugin_run_to_mqtt(self.name, state)
                self.logger.debug('Published to informa/%s via MQTT', self.name)

            # Persist plugin metadata
            self.write_state(state)
            self.logger.debug('Plugin returned %s. State persisted.', ret)

        except AppError as e:
            raise_alarm(self.logger, str(e), e)
        except ValidationError as e:
            raise_alarm(self.logger, 'State ValidationError, possible corruption', e)
        except Exception as e:  # noqa: BLE001
            raise_alarm(self.logger, f'Unhandled exception {e.__class__.__name__}', e)


def publish_plugin_run_to_mqtt(plugin_name: str, state: StateBase):
    'Write plugin\'s output to a MQTT topic'
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.connect('trevor', 1883)
    client.publish(f'informa/{plugin_name}/last_run', state.last_run.isoformat(), retain=True)
    client.publish(f'informa/{plugin_name}/last_count', state.last_count, retain=True)


_click_pass_plugin = click.make_pass_decorator(InformaPlugin)


@click.command('last-run')
@_click_pass_plugin
def plugin_last_run(plugin: InformaPlugin):
    'When was the last run?'
    state = plugin.load_state()
    last_run = arrow.get(state.last_run).humanize() if state.last_run else 'Never'
    print(f'Last run: {last_run} (returned {state.last_count})')


@click.command('run')
@_click_pass_plugin
def plugin_run_now(plugin: InformaPlugin):
    'Run the plugin now in the foreground'
    plugin.execute(sync=True)
