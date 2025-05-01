import logging
import os
import xml.etree.ElementTree as ET
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


def parse_xml_and_download(xml_path: str) -> None:
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Find the first directory in the XML
        first_dir = root.find('.//directory')
        if first_dir is not None:
            path = first_dir.get('path')
            if path:
                download('username', path)  # Replace 'username' with actual username
    except Exception as e:
        logger.error('Failed parsing XML: %s', e)
        raise

def main(state: State) -> int:
    try:
        parse_xml_and_download('coldtea.xml')
        return 0
    except Exception as e:
        logger.error('Failed processing SLSK download: %s', e)
        raise_alarm(logger, f'SLSK error: {e}')
        return 1


def download(username: str, path: str) -> None:
    try:
        client = get_client()
        download_response = client.downloads.enqueue_folder(
            username=username,
            remote_path=path,
            local_path="/Users/mafro/Music"  # Update this path as needed
        )
        logger.info('Download started for %s: %s', path, download_response)
    except Exception as e:
        logger.error('Failed downloading %s: %s', path, e)
        raise


@click.group(name='slsk')
def cli():
    '''Soulseek autodownloader'''


@cli.command
def current():
    '''What is the current HA version?'''
    print(get_client().downloads.get_all())

@cli.command
def download_xml():
    '''Download first directory from coldtea.xml'''
    parse_xml_and_download('coldtea.xml')
