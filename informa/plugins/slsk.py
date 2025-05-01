import logging
import os
from dataclasses import dataclass, field
from typing import List

import click
from slskd_api import SlskdClient

from informa.lib import PluginAdapter, StateBase, app
from informa.lib.plugin import load_run_persist
from informa.lib.utils import raise_alarm


logger = PluginAdapter(logging.getLogger('informa'))


@dataclass
class State(StateBase):
    completed: List[str] = field(default_factory=list)


@app.task('every 1 hour', name=__name__)
def run():
    load_run_persist(logger, State, main)


class MissingSlskdApiKey(Exception):
    pass


def get_client() -> SlskdClient:
    slskd_api_key = os.environ.get('SLSKD_API_KEY')
    if not slskd_api_key:
        raise MissingSlskdApiKey

    return SlskdClient('https://slsk.mafro.net', slskd_api_key)


def main(state: State) -> int:
    try:
        download('popeline', 'path')


    except Exception as e:
        logger.error('Failed checking SLSK status: %s', e)
        raise_alarm(logger, f'SLSK error: {e}')
        return 0


def download(username: str, path: str):
    download_response = get_client().downloads.enqueue_folder(
        username=username,
        remote_path="/path/to/remote/folder",
        local_path="/Users/mafro/Music"
    )


@click.group(name='slsk')
def cli():
    '''Soulseek autodownloader'''


@cli.command
def current():
    'What is the current HA version?'
    print(get_client().downloads.get_all())
