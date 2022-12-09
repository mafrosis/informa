from dataclasses import dataclass, field
import datetime
import logging
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from informa.lib import app, fetch_run_publish, PluginAdapter


logger = PluginAdapter(logging.getLogger('informa'))


MQTT_TOPIC = f'informa/{__name__}'
TEMPLATE_NAME = 'dans.tmpl'


@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)


@app.task('every 12 hours', name=__name__)
def run():
    fetch_run_publish(logger, State, MQTT_TOPIC, main)


def main(state: State):
    logger.debug('Running, last run: %s', state.last_run or 'Never')
    state.last_run = datetime.datetime.now()
