import base64
import binascii
import contextlib
import logging
import os
import tempfile
from pathlib import Path

import click
import eyed3
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from informa import app
from informa.lib import PluginAdapter

logger = PluginAdapter(logging.getLogger('informa'))


MP3HOME = Path(os.environ.get('MP3HOME', '/home/mafro/music/'))


router = APIRouter(prefix='/mp3')


@app.api(router)
def fastapi():
    'Register the APIRouter with Informa'


def find_album_path(query: str) -> Path:
    logger.debug('Lookup: %s', query)

    if (MP3HOME / Path(query)).is_file():
        # If query is an MP3 file, then return path to directory
        return (MP3HOME / Path(query)).parent

    # Search for the directory
    for path in MP3HOME.glob(f'**/{query}'):
        if path.is_dir():
            return path


def try_base64_decode(query: bytes) -> str:
    decoded_query = None

    with contextlib.suppress(binascii.Error):
        decoded_query = base64.b64decode(query)

    if decoded_query is not None:
        try:
            return decoded_query.decode('utf8').strip()
        except UnicodeDecodeError:
            pass

    return query.decode('utf8').strip()


@router.get('/info/{query}')
def get_mp3_album_info(query: bytes):
    path = find_album_path(try_base64_decode(query))
    if path is None:
        return {}

    def count_mp3s(path: Path):
        return sum(1 for x in list(path.glob('*.mp3')))

    urlsafe_identifier = base64.b64encode(path.parts[-1].encode()).decode('utf8')

    return {
        'identifier': path.parts[-1],
        'path': str(path),
        'track_count': count_mp3s(path),
        'artwork_url': f'https://informa.mafro.net/mp3/art/{urlsafe_identifier}',
    }


@router.get('/art/{query}')
def get_mp3_album_art(query: bytes):
    path = find_album_path(try_base64_decode(query))

    if path is None:
        raise HTTPException(status_code=404, detail='Path not found')

    if (path / 'folder.jpg').exists():
        return FileResponse(path / 'folder.jpg', media_type='image/jpeg')
    try:
        # Attempt extract image from first file
        audiofile = eyed3.load(next(iter(path.glob('*.mp3'))))

        # Write to a temporary directory
        for img in audiofile.tag.images:
            if img.mime_type not in eyed3.id3.frames.ImageFrame.URL_MIME_TYPE_VALUES:
                with tempfile.TemporaryDirectory() as tmpdir:
                    with open(f'{tmpdir}/{img.makeFileName()}', 'wb') as f:
                        f.write(img.image_data)

                    return FileResponse(f'{tmpdir}/{img.makeFileName()}', media_type='image/jpeg')
    except StopIteration:
        pass

    raise HTTPException(status_code=404, detail='Artwork missing')


@click.group(name='mp3')
def cli():
    'MP3 toolkit as an API'


@cli.command
@click.argument('query')
def art(query: str):
    '''
    What is the current HA version?

    \b
    QUERY  Artist & album name to lookup
    '''
    print(get_mp3_album_art(query.encode('utf8')))
