from dataclasses import dataclass, field
import datetime
import logging
import re
from typing import cast, Dict, List, Optional

from dataclasses_jsonschema import JsonSchemaMixin
from fake_useragent import UserAgent
import feedparser
import requests

from informa import exceptions
from informa.lib import app, load_run_persist, load_config, mailgun, now_aest, PluginAdapter


logger = PluginAdapter(logging.getLogger('informa'))


PLUGIN_NAME = __name__
TEMPLATE_NAME = 'torrentgalaxy.tmpl'


@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)
    last_seen: Dict[int, str] = field(default_factory=dict)

@dataclass
class Config(JsonSchemaMixin):
    users: List[int]
    terms: List[str]

@dataclass
class Match():
    title: str
    url: str
    magnet: str


@app.task('every 12 hours', name=__name__)
def run():
    load_run_persist(logger, State, PLUGIN_NAME, main)


def main(state: State):
    logger.debug('Running, last run: %s', state.last_run or 'Never')
    state.last_run = now_aest()

    # Reload config each time plugin runs
    config = cast(Config, load_config(Config, __name__))

    sess = requests.Session()

    # Iterate configured torrentgalaxy user IDs
    for uid in config.users:
        query_torrent(sess, config, uid, state.last_seen)


def query_torrent(sess, config: Config, uid: int, last_seen: Dict[int, str]):
    logger.debug('Querying user %s', uid)

    try:
        # Fetch user's RSS feed of uploads
        resp = sess.get(
            f'https://torrentgalaxy.to/rss?magnet&user={uid}',
            headers={'User-Agent': UserAgent().chrome},
            timeout=5,
        )
    except requests.RequestException as e:
        logger.error('Failed loading torrentgalaxy for %s: %s', uid, e)
        return

    feed = feedparser.parse(resp.text)

    try:
        for searchterm in config.terms:
            matches = []

            # Compile each search term as a regex
            pat = re.compile(searchterm, re.IGNORECASE)

            # Iterate the torrents in the RSS feed
            for entry in feed['entries']:
                # When we reach last seen, abort processing
                if entry['id'] == last_seen.get(uid, 0):
                    raise exceptions.ReachedLastSeen(entry['title'])

                # Pattern match terms
                match = re.search(pat, entry['title'])
                if match:
                    matches.append(
                        Match(entry['title'], entry['comments'], entry['links'][0]['href'])
                    )

            if matches:
                # Notify all matches per search term
                mailgun.send(
                    logger,
                    f'Torrents found for {searchterm}',
                    TEMPLATE_NAME,
                    {
                        'term': searchterm,
                        'matches': matches,
                    }
                )
                logger.debug('Sent email for %s', searchterm)

    except exceptions.ReachedLastSeen as e:
        logger.debug(e)
    finally:
        # Track the first entry seen, so we can skip these next time
        logger.debug('Marking last seen: %s', feed['entries'][0]['title'])
        last_seen[uid] = feed['entries'][0]['id']
