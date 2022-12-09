from dataclasses import dataclass, field
import datetime
import json
import logging
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin
import paho.mqtt.client as mqtt

from informa.lib import app, MQTT_BROKER, PluginAdapter


logger = PluginAdapter(logging.getLogger('informa'))


MQTT_TOPIC = f'informa/{__name__}'
TEMPLATE_NAME = 'dans.tmpl'


@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)


@app.task('every 1 day')
def fetch_state_and_run():
    client = mqtt.Client()

    def on_message(_1, _2, msg: mqtt.MQTTMessage):
        logger.debug('State retrieved')

        # Pass plugin state into main run function
        state = State.from_dict(json.loads(msg.payload))
        main(state)

        # Publish plugin state back to MQTT
        client.publish(MQTT_TOPIC, state, retain=True)

        client.loop_stop()

    # Connect to MQTT to retrieve plugin state
    client.on_message = on_message
    client.connect(MQTT_BROKER)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()

    logger.debug('Subscribed to %s', MQTT_TOPIC)


def main(state: State):
    logger.debug('Running, last run: %s', state.last_run or 'Never')
    state.last_run = datetime.datetime.now()
