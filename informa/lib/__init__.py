import abc
import datetime
import inspect
import logging
from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin


class ConfigBase(DataClassJsonMixin, abc.ABC):
    'Base class from which plugin Config classes must inherit'

@dataclass
class StateBase(DataClassJsonMixin):
    'Base class from which plugin State classes must inherit'

    last_run: datetime.datetime | None = None
    last_count: int | None = None


class PluginAdapter(logging.LoggerAdapter):
    "Logging wrapper which prepends a plugin's name before each log entry"
    def __init__(self, logger_, plugin_name: str | None = None):
        if plugin_name is None:
            # Automatically determine plugin name from calling class
            plugin_name = inspect.getmodule(inspect.stack()[1][0]).__name__.split('.')[-1]

        super().__init__(logger_, plugin_name.upper())

    def process(self, msg, kwargs=None):
        return f'[{self.extra}] {msg}', kwargs
