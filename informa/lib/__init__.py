import os
from rocketry import Rocketry


app = Rocketry(config={'execution': 'thread'})

MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
