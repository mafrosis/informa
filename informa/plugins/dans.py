from dataclasses import dataclass, field
import datetime
import json
import logging

from dataclasses_jsonschema import JsonSchemaMixin
import paho.mqtt.client as mqtt

from informa.lib import app


logger = logging.getLogger('informa')


MQTT_BROKER = 'ringil'
MQTT_TOPIC = f'informa/{__name__}'
TEMPLATE_NAME = 'dans.tmpl'


@dataclass
class State(JsonSchemaMixin):
    last_run: datetime.date = field(default=datetime.datetime.now())


@app.task('every 1 day')
def fetch_state_and_run():
    client = mqtt.Client()

    def on_message(_1, _2, msg: mqtt.MQTTMessage):
        logger.debug('State retrieved')
        state = State.from_dict(json.loads(msg.payload))
        run(state)

        client.loop_stop()

    client.on_message = on_message
    client.connect(MQTT_BROKER)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()

    logger.debug('Subscribed to %s', MQTT_TOPIC)


def run(state: State):
    logger.debug('Running, last run: %s', state.last_run)
