import importlib
import json
import os
import logging

import paho.mqtt.client as mqtt
import yaml

from informa.lib import app, MQTT_BROKER


logger = logging.getLogger('informa')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.INFO)

if os.environ.get('DEBUG'):
    logger.setLevel(logging.DEBUG)


def main():
    init_plugins()
    app.run()


def init_plugins():
    # Load active plugins from YAML config
    with open('plugins.yaml', encoding='utf8') as f:
        plugins = yaml.safe_load(f)['plugins']

    client = mqtt.Client()

    def on_message(_1, _2, msg: mqtt.MQTTMessage):
        # Retrieved message is the list of active plugins
        known_plugins = json.loads(msg.payload)

        # Iterate loaded plugins
        for plug in plugins:
            # Dynamic import to register rocketry tasks
            importlib.import_module(f'informa.plugins.{plug}')

            if not plug in known_plugins:
                logger.debug('Initialising plugin %s', plug)

                # Ensure plugin initial state is present in MQTT
                client.publish(f'informa/informa.plugins.{plug}', '{}', retain=True)

            if plug not in known_plugins:
                known_plugins.append(plug)

        # Track list of known plugins in MQTT
        client.publish('informa/plugins', json.dumps(known_plugins), retain=True)

        client.loop_stop()

    client.on_message = on_message
    client.connect(MQTT_BROKER)
    client.subscribe('informa/plugins')
    logger.debug('Ensure you have initialised the "informa" topic, else the program will hang..')
    client.loop_start()
