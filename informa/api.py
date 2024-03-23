import os
import pathlib

from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware

from informa.lib import fastapi as app_fastapi, app as app_rocketry


MP3HOME=os.environ.get('MP3PATH', '/home/mafro/music/')


# CORS support for React frontends
app_fastapi.add_middleware(
    CORSMiddleware,
    allow_origins=['https://informa.mafro.net', 'http://localhost:3000'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


######
# Session Config API
#
router_config = APIRouter(tags=['config'])

@router_config.get('/session/config')
async def get_session_config():
    return {
        'execution': app_rocketry.session.config.execution,
        'timezone': str(app_rocketry.session.config.timezone),
        'cycle_sleep': app_rocketry.session.config.cycle_sleep,
        'task_priority': app_rocketry.session.config.task_priority,
        'timeout': app_rocketry.session.config.cycle_sleep,
        'restarting': app_rocketry.session.config.restarting,
        'instant_shutdown': app_rocketry.session.config.instant_shutdown,
        'max_process_count': app_rocketry.session.config.max_process_count,
        'multilaunch': app_rocketry.session.config.multilaunch,
        'debug': app_rocketry.session.config.debug,
    }

@router_config.patch('/session/config')
async def patch_session_config(values: dict):
    for key, val in values.items():
        setattr(app_rocketry.session.config, key, val)


app_fastapi.include_router(router_config)


######
# MP3 album info API
#
router_mp3info = APIRouter(prefix='/mp3', tags=['mp3info'])

@router_mp3info.get('/info/{identifier}')
async def get_mp3_album_info(identifier: str):
    def count_mp3s(dirpath: str):
        return sum(1 for f in os.listdir(dirpath) if f.endswith('mp3'))

    def find_album_path(albumartist: str):
        for path in pathlib.Path(MP3HOME).glob(f'**/{albumartist}'):
            if path.is_dir():
                return str(path)

    path = find_album_path(identifier)

    return {
        'identifier': identifier,
        'path': path,
        'track_count': count_mp3s(path),
    }

@router_mp3info.get('/art/{identifier}')
async def get_mp3_album_art(identifier: str):
    def find_album_art_path(albumartist: str):
        for path in pathlib.Path(MP3HOME).glob(f'**/{albumartist}'):
            if os.exists(f'{path}/folder.jpg'):
                return f'{path}/folder.jpg'

    path = find_album_art_path(identifier)

    with open(path, 'rb') as f:
        return f.read()


app_fastapi.include_router(router_mp3info)
