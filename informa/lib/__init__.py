import abc
import datetime
import decimal
import inspect
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, TypeVar, cast

import click
import orjson
import yaml
from dataclasses_json import DataClassJsonMixin
from fastapi import APIRouter
from paho.mqtt import publish as mqtt_publish

from informa.exceptions import StateJsonDecodeError

F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class InformaTask:
    func: F
    condition: str


@dataclass
class InformaPlugin:
    module: ModuleType
    tasks: list[InformaTask] = field(default_factory=list)
    api: APIRouter | None = None
    _logger: logging.Logger | None = None
    _state_cls: type | None = None
    _config_cls: type | None = None
    _main: Callable | None = None

    @property
    def name(self):
        return self.module.__name__

    @property
    def cli(self):
        for _, member in inspect.getmembers(self.module):
            if isinstance(member, click.core.Group):
                return member

    @property
    def logger(self):
        def get_plugin_logger():
            'Return the class attribute which is an instance of lib.PluginAdapter'
            return next(iter([v for _, v in inspect.getmembers(self.module) if isinstance(v, PluginAdapter)]), None)

        return get_plugin_logger()

    @property
    def state_cls(self):
        return self.get_class_attr(StateBase)

    @property
    def config_cls(self):
        return self.get_class_attr(ConfigBase)

    @property
    def main_func(self):
        return self.module.main

    def get_class_attr(self, type_):
        'Return the class type defined in the plugin, which inherits from `type_`'
        clss = [
            v for _, v in inspect.getmembers(self.module, inspect.isclass) if issubclass(v, type_) and v is not type_
        ]
        return next(iter(clss), None)

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
            hostname='locke',
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
            hostname='locke',
            retain=True,
        )


class PluginAdapter(logging.LoggerAdapter):
    def __init__(self, logger_, plugin_name: str | None = None):
        if plugin_name is None:
            # Automatically determine plugin name from calling class
            plugin_name = inspect.getmodule(inspect.stack()[1][0]).__name__.split('.')[-1]

        super().__init__(logger_, plugin_name.upper())

    def process(self, msg, kwargs=None):
        return f'[{self.extra}] {msg}', kwargs


class ConfigBase(DataClassJsonMixin, abc.ABC):
    'Base class from which plugin Config classes must inherit'


@dataclass
class StateBase(DataClassJsonMixin):
    'Base class from which plugin State classes must inherit'

    last_run: datetime.datetime | None = None
    last_count: int | None = None


def pass_plugin_name(func):
    'Lookup the name of the calling module, and pass as the first parameter to `func`'

    def inner(*args, **kwargs):
        frame = inspect.stack()[1]
        plugin_name = inspect.getmodule(frame[0]).__name__
        return func(plugin_name, *args, **kwargs)

    return inner


def _load_config(plugin_name: str, config_cls: type[ConfigBase] | None) -> DataClassJsonMixin | None:
    '''
    Load plugin config
    '''
    if config_cls is None:
        return None

    try:
        config_dir = os.environ.get('CONFIG_DIR', './config')

        with open(f'{config_dir}/{plugin_name}.yaml', encoding='utf8') as f:
            data = yaml.load(f, Loader=yaml.Loader)  # noqa: S506
            if not data:
                return None
    except FileNotFoundError:
        return None

    return cast(ConfigBase, config_cls.from_dict(data))


def _load_state(
    plugin_name: str, logger: logging.Logger | logging.LoggerAdapter, state_cls: type[StateBase]
) -> StateBase:
    '''
    Load or initialise plugin state
    '''
    try:
        state_dir = os.environ.get('STATE_DIR', './state')

        with open(f'{state_dir}/{plugin_name}.json', encoding='utf8') as f:
            data = orjson.loads(f.read())
            if not data:
                raise StateJsonDecodeError

        # Inflate JSON into the State dataclass
        state = state_cls.from_dict(data)

    except (FileNotFoundError, orjson.JSONDecodeError):
        logger.debug('Empty state initialised for %s', plugin_name)
        state = state_cls()

    logger.debug('Loaded state for %s', plugin_name)

    return cast(StateBase, state)


def _write_state(plugin_name: str, state_obj: StateBase):
    '''
    Utility function to write state to a file
    '''
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

    with open(f'{state_dir}/{plugin_name}.json', 'w', encoding='utf8') as f:
        f.write(orjson.dumps(state_obj, default=default).decode())
