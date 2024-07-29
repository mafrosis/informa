import base64
import binascii
import contextlib
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from informa.lib import PluginAdapter
from informa.lib import fastapi as app_fastapi

logger = PluginAdapter(logging.getLogger('informa'))


MP3HOME = Path(os.environ.get('MP3HOME', '/home/mafro/music/'))


router = APIRouter(prefix='/mp3')


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
    with contextlib.suppress(binascii.Error):
        query = base64.b64decode(query)
    return query.decode('utf8').strip()


@router.get('/info/{query}')
def get_mp3_album_info(query: bytes):
    path = find_album_path(try_base64_decode(query))

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

    if (path / 'folder.jpg').exists():
        return FileResponse(path / 'folder.jpg', media_type='image/jpeg')

    raise HTTPException(status_code=404, detail='Artwork missing')


app_fastapi.include_router(router)
