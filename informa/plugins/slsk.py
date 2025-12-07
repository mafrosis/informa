import contextlib
import datetime
import functools
import json
import logging
import os
import pathlib
import time
from dataclasses import dataclass, field

import click
import polars as pl
import pytz
import requests
from slskd_api import SlskdClient

from informa import app
from informa.lib import ConfigBase, PluginAdapter, StateBase, pretty
from informa.lib.plugin import InformaPlugin

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
    completed: dict[str, dict[str, list[str]]] = field(default_factory=dict)  # username -> pattern -> list[albums]
    users: dict[str, User] = field(default_factory=dict)


class MissingSlskdApiKey(Exception):
    pass


@app.task('every 6 hours')
def run(plugin):
    plugin.execute()


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
    for username in list(state.users.keys()):
        if username not in config.users:
            del state.users[username]

    total = 0

    try:
        num_albums = int(os.environ.get('SLSKD_NUM_ALBUMS', 1))
    except ValueError:
        num_albums = 2

    for user in state.users.values():
        # Browse and cache files for configured users
        df = fetch_user_file_listing(user)

        if df is None:
            continue

        for pattern in config.patterns:
            # Match and download $SLSKD_NUM_ALBUMS directories per run
            matches = df.filter(pl.col('dir_path').str.contains(pattern))
            if matches.is_empty():
                matches = df.filter(pl.col('folder_name').str.contains(pattern))
                if matches.is_empty():
                    continue

            # Add this filter to exclude completed folders
            matches = matches.filter(
                ~pl.col('folder_name').is_in(state.completed.get(user.username, {}).get(pattern, []))
            )
            if matches.is_empty():
                logger.info('Nothing to download from %s with pattern %s', user.username, pattern)
                continue

            # Find first $SLSKD_NUM_ALBUMS albums
            albums = matches.group_by('folder_name').first().sort(['dir_path', 'folder_name']).head(num_albums)

            for row in albums.iter_rows(named=True):
                logger.info('Matched %s from %s', row['folder_name'], user.username)

                # Queue all files from each album, by deserializing the JSON in the files column
                if count := enqueue_download(user.username, json.loads(row['files'])):
                    # Record in state as done
                    if user.username not in state.completed:
                        state.completed[user.username] = {}

                    if pattern not in state.completed[user.username]:
                        state.completed[user.username][pattern] = []

                    state.completed[user.username][pattern].append(row['folder_name'])

                    # Give slskd a moment
                    time.sleep(1)

                total += count

    return total


def slskd_ca_context(func):
    '''
    Decorator which temporarily sets REQUESTS_CA_BUNDLE from CA_CERT environment variable.
    Restores original environment setting on exit.
    '''

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        original_ca = os.environ.get('REQUESTS_CA_BUNDLE')
        slskd_ca = os.environ.get('CA_CERT')

        if not slskd_ca:
            logger.warning('CA_CERT not set, skipping certificate override')
            return func(*args, **kwargs)

        try:
            os.environ['REQUESTS_CA_BUNDLE'] = slskd_ca
            logger.debug('Temporarily set REQUESTS_CA_BUNDLE to CA_CERT: %s', slskd_ca)
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
def fetch_user_file_listing(user: User) -> pl.DataFrame | None:
    '''
    Fetch and process user's file listing from Soulseek using slskd API.
    Returns a DataFrame with individual audio files as rows.
    '''
    now_au = datetime.datetime.now(pytz.timezone('Australia/Melbourne'))

    # Return cached data if valid
    if (
        user.date_fetched
        and user.date_fetched > (now_au - datetime.timedelta(days=7))
        and pathlib.Path(user.cached_path).exists()
    ):
        logger.info('Loading cached files for user: %s', user.username)
        return pl.read_ipc(user.cached_path)

    logger.info('Fetching files for user: %s', user.username)
    entries = []

    try:
        browse_result = get_client().users.browse(user.username)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            logger.error('It appears user %s is offline', user.username)
        else:
            logger.error('A HTTP error occurred browsing %s (%s)', user.username, e.response.status_code)
        return None
    except requests.exceptions.JSONDecodeError as e:
        logger.error('Failed to browse files for user %s: %s', user.username, e)
        return None

    def process(directories):
        total = 0
        for directory in directories:
            dir_path = pathlib.Path(directory['name'].replace('\\', '/'))

            # Check if directory contains audio files
            has_audio = any(file['filename'].lower().endswith(('.mp3', '.flac')) for file in directory['files'])

            if has_audio:
                for file in directory['files']:
                    file['filename'] = str(dir_path / file['filename'])

                entries.append(
                    {
                        'dir_path': str(dir_path.parent),
                        'folder_name': dir_path.name,
                        'files': json.dumps(directory['files']),
                    }
                )
                total += len(directory['files'])
        return total

    total_files = process(browse_result['directories'])

    df = pl.DataFrame(entries)
    if not df.is_empty():
        df.write_ipc(f'{user.username}.feather')
        user.date_fetched = now_au
        user.cached_path = str(pathlib.Path(f'{user.username}.feather').absolute())

    logger.debug('Found %d directories, %d files', df.height, total_files)
    return df


@slskd_ca_context
def enqueue_download(username: str, files: list) -> int:
    '''
    Enqueues downloads from a specific user using the slskd API.

    Args:
        username: The Soulseek username of the person to download from.
        files: A list of objects from the slskd search/browse APIs.
    Returns:
        bool on success
    '''
    try:
        get_client().transfers.enqueue(username=username, files=files)

    except requests.exceptions.HTTPError as e:
        logger.error('500 error: %s', e.response.json())
        return 0
    except requests.exceptions.ConnectionError:
        logger.error('SLSKD appears to be down!')
        return 0
    else:
        logger.info('Enqueued %d files from %s', len(files), username)
        return len(files)


@click.group(name='slsk')
def cli():
    '''Soulseek autodownloader'''


@cli.command
@click.argument('user')
def view_files(plugin: InformaPlugin, user: str):
    '''
    List a user\'s files in the terminal

    \b
    USER  slsk username
    '''
    state = plugin.load_state()
    if user not in state.users:
        print('Unknown user')
        return

    # Hide polars DataFrame header, display all rows, display full text
    pl.Config.set_tbl_hide_dataframe_shape(True)
    pl.Config.set_tbl_rows(-1)
    pl.Config.set_fmt_str_lengths(300)

    df = pl.read_ipc(state.users[user].cached_path)
    print(df.select(['folder_name', 'dir_path']))


@cli.command
@click.argument('user')
def view_completed(plugin: InformaPlugin, user: str):
    '''
    List completed downloads for a user

    \b
    USER  slsk username
    '''
    state = plugin.load_state()
    if user not in state.users:
        print('Unknown user')
        return

    for pattern, albums in state.completed[user].items():
        pretty.table(albums, title=pattern, columns=('album',))


@cli.command
@click.argument('user')
@click.argument('album')
def remove_completed(plugin: InformaPlugin, user: str, album: str):
    '''
    Remove an album from the completed downloads for a user

    \b
    USER   slsk username
    ALBUM  album name (exact match) to remove
    '''
    state = plugin.load_state()

    if user not in state.users:
        raise click.ClickException(f'Unknown user: {user}')

    if user not in state.completed or not state.completed[user]:
        raise click.ClickException(f'User {user} has no completed albums')

    if album not in state.completed[user]:
        raise click.ClickException(f'Album {album} not found in completed list for {user}')

    # Remove the album
    state.completed[user].remove(album)

    # Remove user entry if no completed albums remain
    if not state.completed[user]:
        del state.completed[user]

    # Persist changes
    plugin.write_state(state)
    click.echo(f'Removed {album} from {user}\'s completed list')


@cli.command
@click.argument('old_username')
@click.argument('new_username')
def rename_user(plugin: InformaPlugin, old_username: str, new_username: str):
    '''
    Rename a username in state

    \b
    OLD_USERNAME  current username in state
    NEW_USERNAME  replacement username
    '''
    state = plugin.load_state()

    if old_username not in state.users:
        raise click.ClickException(f'Unknown user: {old_username}')
    if new_username in state.users:
        raise click.ClickException(f'Username already exists: {new_username}')

    # Rename the user, and clear the cached path
    user_obj = state.users.pop(old_username)
    user_obj.username = new_username
    user_obj.cached_path = None
    user_obj.date_fetched = None
    state.users[new_username] = user_obj

    # Update completed dict
    if old_username in state.completed:
        state.completed[new_username] = state.completed.pop(old_username)

    # Persist changes
    plugin.write_state(state)
    click.echo(f'Renamed {old_username} to {new_username}')


@cli.command
@click.argument('username')
@click.argument('old_pattern')
@click.argument('new_pattern')
def rename_user_pattern(plugin: InformaPlugin, username: str, old_pattern: str, new_pattern: str):
    '''
    Rename a search pattern on completed downloads for a user

    \b
    USERNAME     slsk username
    OLD_PATTERN  current pattern with completed albums
    NEW_PATTERN  replacement pattern
    '''
    state = plugin.load_state()
    if username not in state.completed or not state.completed[username]:
        raise click.ClickException(f'No completed albums found for {username}')

    if old_pattern not in state.completed[username]:
        click.echo(f'Valid patterns for {username}:')
        for pat in state.completed[username]:
            click.echo(f' - {pat}')
        raise click.ClickException('Invalid pattern supplied')

    # Pull the completed albums for old_pattern and reinsert with new_pattern
    state.users[new_pattern] = state.completed[username].pop(old_pattern)

    # Persist changes
    plugin.write_state(state)
    click.echo(f'Renamed {old_pattern} to {new_pattern} for {username}')


@cli.command
def list_users(plugin: InformaPlugin):
    '''
    List all configured users without state details
    '''
    config = plugin.load_config()
    if not config.users:
        click.echo('No users configured')
        return

    click.echo('Configured users:')
    for user in config.users:
        click.echo(f'  {user}')


@cli.command
@click.argument('username')
def delete_cache(plugin: InformaPlugin, username: str):
    '''
    Delete cached feather file for a user (will be re-fetched on next run)

    \b
    USERNAME  slsk username
    '''
    state = plugin.load_state()
    if username not in state.users:
        raise click.ClickException(f'Unknown user: {username}')

    user = state.users[username]
    if not user.cached_path or not pathlib.Path(user.cached_path).exists():
        raise click.ClickException(f'No cached file found for {username}')

    # Delete the cached feather file
    cached_file = pathlib.Path(user.cached_path)
    cached_file.unlink()

    # Clear cache metadata in state
    user.cached_path = None
    user.date_fetched = None

    # Persist changes
    plugin.write_state(state)
    click.echo(f'Deleted cache for {username}')


@cli.command
@click.argument('username')
@click.argument('pattern')
@click.argument('directory', type=click.Path(file_okay=False, path_type=pathlib.Path))
@click.option('--dry-run', is_flag=True, default=False, help='Non destructive dry run to see stats')
def verify_completed(plugin: InformaPlugin, username: str, pattern: str, directory: pathlib.Path, dry_run: bool):
    '''
    Verify completed albums exist on disk and sync state accordingly.
    Removes missing entries from state and adds albums found on disk.

    \b
    USERNAME   slsk username
    PATTERN    album search pattern
    DIRECTORY  directory containing downloaded albums
    '''
    state = plugin.load_state()

    # Ensure user exists in state
    if username not in state.users:
        raise click.ClickException(f'Unknown user: {username}')

    # Initialize completed structure if needed
    if username not in state.completed:
        state.completed[username] = {}
    if pattern not in state.completed[username]:
        state.completed[username][pattern] = []

    # Filter the user's library for albums matching pattern
    df = pl.read_ipc(state.users[username].cached_path)
    df = df.filter(pl.col('dir_path').str.contains(pattern))

    # Track missing and found albums
    missing = set()
    found_on_disk = set()

    # Check albums in state that are missing from disk
    for album in state.completed[username][pattern]:
        album_rows = df.filter(pl.col('folder_name') == album)
        if album_rows.is_empty():
            # Album not in user's library anymore
            missing.add(album)
            continue

        files = json.loads(album_rows['files'][0])

        for fn in [pathlib.Path(f['filename']).name for f in files]:
            if not (directory / album / fn).exists():
                missing.add(album)
                break

    # Check for albums on disk that are not in state
    current_completed = set(state.completed[username][pattern])
    all_albums_in_library = set(df['folder_name'].unique().to_list())

    for album in all_albums_in_library:
        if album in current_completed:
            continue

        # Check if this album exists fully on disk
        album_dir = directory / album
        if not album_dir.exists():
            continue

        files = json.loads(df.filter(pl.col('folder_name') == album)['files'][0])
        all_files_present = all((directory / album / pathlib.Path(f['filename']).name).exists() for f in files)

        if all_files_present:
            found_on_disk.add(album)

    # Display summary
    click.echo(
        f"{'DRY RUN -- ' if dry_run else ''}Total in state: {len(state.completed[username][pattern])}, "
        f'Missing: {len(missing)}, Found on disk: {len(found_on_disk)}'
    )

    if dry_run and missing:
        click.echo('Missing albums:')
        for album in sorted(missing):
            click.echo(f'  {album}')

    if not dry_run and (missing or found_on_disk):
        # Remove missing albums
        if missing:
            state.completed[username][pattern] = list(set(state.completed[username][pattern]) - missing)

        # Add found albums
        if found_on_disk:
            state.completed[username][pattern].extend(list(found_on_disk))

        # Clean up empty pattern
        if not state.completed[username][pattern]:
            del state.completed[username][pattern]

        # Persist changes
        plugin.write_state(state)

        if missing:
            click.echo('Removed missing albums:')
            for album in sorted(missing):
                click.echo(f'  {album}')

        if found_on_disk:
            click.echo('Added albums found on disk:')
            for album in sorted(found_on_disk):
                click.echo(f'  {album}')
