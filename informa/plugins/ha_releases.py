from dataclasses import dataclass, field
import datetime
import logging
from typing import Optional

import bs4
from dataclasses_jsonschema import JsonSchemaMixin
import requests

from informa.lib import app, load_run_persist, mailgun, now_aest, PluginAdapter


logger = PluginAdapter(logging.getLogger('informa'))


PLUGIN_NAME = __name__
TEMPLATE_NAME = 'ha.tmpl'


@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)
    last_release_seen: Optional[str] = field(default=None)


@app.task('every 12 hours', name=__name__)
def run():
    load_run_persist(logger, State, PLUGIN_NAME, main)


def main(state: State):
    logger.debug('Running, last run: %s', state.last_run or 'Never')
    state.last_run = now_aest()

    state.last_release_seen = fetch_ha_releases(state.last_release_seen or None)


def fetch_ha_releases(last_release_seen: Optional[str]):
    try:
        # Fetch release notes page
        resp = requests.get('https://www.home-assistant.io/blog/categories/release-notes/', timeout=5)
    except requests.RequestException as e:
        logger.error('Failed loading HA release notes: %s', e)
        return False

    # Parse the HTML and compare latest release to last seen
    soup = bs4.BeautifulSoup(resp.text, 'html.parser')

    for release in soup.select('h1.gamma a'):
        try:
            version = release.text.split(':')[0]
        except IndexError:
            continue

        if version == last_release_seen:
            logger.debug('Stopping at %s', version)
            break

        if version > (last_release_seen or '0'):
            # Parse release title (this is likely to break at some point)
            last_release_seen = version
            logger.info('Found %s', last_release_seen)

            mailgun.send(
                logger,
                f'New HA release {last_release_seen}',
                TEMPLATE_NAME,
                {
                    'version': last_release_seen,
                }
            )
            break

    return last_release_seen
