import base64
import binascii
import contextlib
import logging
import os
from pathlib import Path

from fastapi import APIRouter

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

    return {
        'identifier': path.parts[-1],
        'path': str(path),
        'track_count': count_mp3s(path),
    }


app_fastapi.include_router(router)
