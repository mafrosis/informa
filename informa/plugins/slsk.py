import contextlib
import datetime
import functools
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import click
import pandas as pd
import pytz
import requests
from slskd_api import SlskdClient

from informa import app
from informa.lib import ConfigBase, PluginAdapter, StateBase, pretty
from informa.lib.plugin import load_run_persist, load_state

logger = PluginAdapter(logging.getLogger('informa'))


@dataclass
class Config(ConfigBase):
    users: list[str]
    patterns: list[str]


@dataclass
class User:
    username: str
    cached_path: str | None = None
    date_fetched: datetime.datetime | None = None


@dataclass
class State(StateBase):
    completed: list[str] = field(default_factory=list)
    users: dict[str, User] = field(default_factory=dict)  # Changed to dict


class MissingSlskdApiKey(Exception):
    pass


@app.task('every 1 hour')
def run():
    load_run_persist(logger, State, main)


def get_client() -> SlskdClient:
    slskd_api_key = os.environ.get('SLSKD_API_KEY')
    if not slskd_api_key:
        raise MissingSlskdApiKey

    return SlskdClient('https://slsk.mafro.net', slskd_api_key)


def main(state: State, config: Config) -> int:
    # Load configured users into plugin state
    for username in config.users:
        if username not in state.users:
            state.users[username] = User(username)

    # Remove users from state if removed from config
    for username in list(state.users.keys()):  # Create copy to mutate during iteration
        if username not in config.users:
            del state.users[username]

    for user in state.users.values():  # Iterate over dict values
        # browse and cache files for configured users
        df = fetch_user_file_listing(user)

        # iterate each pattern
        for pattern in config.patterns:
            # Match and download 2 directories per run
            matches = df[df['folder_name'].str.contains(pattern, regex=True)]
            if matches.empty:
                continue

            # Find first two albums
            albums = matches.groupby('folder_name').head(1)['folder_name'].head(2).to_list()

            # Queue all files from the two albums
            to_download = matches[matches.folder_name.isin(albums)]['files'].to_list()
            for file_set in to_download:
                enqueue_download(user.username, json.loads(file_set))


def slskd_ca_context(func):
    '''
    Decorator which temporarily sets REQUESTS_CA_BUNDLE from SLSKD_CA_CERT environment variable.
    Restores original environment setting on exit.
    '''

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        original_ca = os.environ.get('REQUESTS_CA_BUNDLE')
        slskd_ca = os.environ.get('SLSKD_CA_CERT')

        if not slskd_ca:
            logger.warning('SLSKD_CA_CERT not set, skipping certificate override')
            return func(*args, **kwargs)

        try:
            os.environ['REQUESTS_CA_BUNDLE'] = slskd_ca
            logger.debug('Temporarily set REQUESTS_CA_BUNDLE to SLSKD_CA_CERT: %s', slskd_ca)
            return func(*args, **kwargs)
        finally:
            if original_ca is not None:
                os.environ['REQUESTS_CA_BUNDLE'] = original_ca
                logger.debug('Restored REQUESTS_CA_BUNDLE to original value: %s', original_ca)
            else:
                with contextlib.suppress(KeyError):
                    del os.environ['REQUESTS_CA_BUNDLE']
                    logger.debug('Removed REQUESTS_CA_BUNDLE environment variable')

    return wrapper


@slskd_ca_context
def fetch_user_file_listing(user: User) -> pd.DataFrame:
    '''
    Fetch and process user's file listing from Soulseek using slskd API.
    Returns a DataFrame with individual audio files as rows.
    '''
    now_au = datetime.datetime.now(pytz.timezone('Australia/Melbourne'))

    # Return cached data if valid
    if (
        user.date_fetched
        and user.date_fetched > (now_au - datetime.timedelta(days=7))
        and Path(user.cached_path).exists()
    ):
        logger.info('Loading cached files for user: %s', user.username)
        return pd.read_feather(user.cached_path)

    logger.info('Fetching files for user: %s', user.username)
    entries = []

    try:
        client = get_client()
        browse_result = client.users.browse(user.username)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            logger.error('It appears user %s is offline', user.username)
        else:
            logger.error('A HTTP error occurred browsing %s (%s)', user.username, e.response.status_code)
        return None
    except requests.exceptions.JSONDecodeError as e:
        logger.error('Failed to browse files for user %s: %s', user.username, e)
        return pd.DataFrame(columns=['folder_name', 'files'])

    def process(directories):
        total = 0
        for directory in directories:
            dir_path = Path(directory['name'].replace('\\', '/'))

            # Check if directory contains audio files
            has_audio = any(file['filename'].lower().endswith(('.mp3', '.flac')) for file in directory['files'])

            if has_audio:
                for file in directory['files']:
                    file['filename'] = str(dir_path / file['filename'])

                entries.append({'folder_name': dir_path.name, 'files': json.dumps(directory['files'])})
                total += len(directory['files'])
        return total

    total_files = process(browse_result['directories'])

    df = pd.DataFrame(entries)
    if not df.empty:
        df.to_feather(f'{user.username}.feather')
        user.date_fetched = now_au
        user.cached_path = f'{user.username}.feather'

    logger.debug('Found %d directories, %d files', len(df), total_files)
    return df


@slskd_ca_context
def enqueue_download(username: str, files: list) -> bool:
    '''
    Enqueues downloads from a specific user using the slskd API.

    Args:
        username: The Soulseek username of the person to download from.
        files: A list of objects from the slskd search/browse APIs.
    Returns:
        bool on success
    '''
    try:
        logger.info('Attempting to enqueue %d files from user %s', len(files), username)
        get_client().transfers.enqueue(username=username, files=files)

    except requests.exceptions.HTTPError as e:
        logger.error('Failed to enqueue downloads: %s', e)
        return False
    else:
        logger.info('Successfully enqueued %d files from %s', len(files), username)
        return True


@click.group(name='slsk')
def cli():
    '''Soulseek autodownloader'''


@cli.command
@click.argument('user')
def view_files(user: str):
    '''
    List a user\'s files in the terminal

    \b
    USER  slsk username
    '''
    state = load_state(logger, State)
    if user not in state.users:
        print('Unknown user')
        return

    df = pd.read_feather(state.users[user].cached_path)
    pretty.dataframe(df)
