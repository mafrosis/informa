import datetime
import inspect
import json
import logging
import os
from typing import Callable, Type, Union
from zoneinfo import ZoneInfo

from dataclasses_jsonschema import JsonSchemaMixin
import paho.mqtt.client as mqtt
from rocketry import Rocketry

from informa.exceptions import AppError


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


def fetch_run_publish(
        logger: Union[logging.Logger, logging.LoggerAdapter],
        state_cls: Type[JsonSchemaMixin],
        mqtt_topic: str,
        main_func: Callable
    ):
    '''
    Fetch MQTT state, run a callback, and publish the state back to MQTT.

    Params:
        logger:      Logger for the calling plugin
        state_cls:   Dataclass model of the JSON state persisted in MQTT
        mqtt_topic:  Plugin MQTT topic
        main_func:   Callback function to trigger plugin logic
    '''
    client = mqtt.Client()

    def on_message(_1, _2, msg: mqtt.MQTTMessage):
        logger.debug('State retrieved')

        # Pass plugin state into main run function
        state = state_cls.from_dict(json.loads(msg.payload))

        try:
            main_func(state)

            # Publish plugin state back to MQTT
            client.publish(mqtt_topic, json.dumps(state.to_dict()), retain=True)
            logger.debug('State published')

        except AppError as e:
            logger.error(str(e))

        client.loop_stop()

    # Connect to MQTT to retrieve plugin state
    client.on_message = on_message
    client.connect(MQTT_BROKER)
    client.subscribe(mqtt_topic)
    client.loop_start()

    logger.debug('Subscribed to %s', mqtt_topic)


def now_aest() -> datetime.datetime:
    'Utility function to return now as TZ-aware datetime'
    return datetime.datetime.now(ZoneInfo('Australia/Melbourne'))