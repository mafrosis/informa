import inspect
import logging
import os

from rocketry import Rocketry


app = Rocketry(config={'execution': 'thread'})

MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')


class PluginAdapter(logging.LoggerAdapter):
    def __init__(self, logger_, extra=None):
        super().__init__(
            logger_,
            inspect.getmodule(inspect.stack()[1][0]).__name__.split('.')[-1].upper()
        )

    def process(self, msg, kwargs):
        return f'[{self.extra}] {msg}', kwargs
