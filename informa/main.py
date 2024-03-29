import functools
import importlib
import inspect
import logging
from types import ModuleType
from typing import Dict

import asyncio
from fastapi import APIRouter
import uvicorn
import yaml

from informa.api import app_fastapi
from informa.lib import app as app_rocketry


logger = logging.getLogger('informa')


@functools.lru_cache()
def init_plugins() -> Dict[str, ModuleType]:
    # Load active plugins from YAML config
    with open('plugins.yaml', encoding='utf8') as f:
        plugins = yaml.safe_load(f)['plugins']

    modules = {}

    for plug in plugins:
        # Convert dashes into underscores for python imports
        module_name = plug.replace('-', '_')

        try:
            # Dynamic import to register rocketry tasks
            modules[plug] = importlib.import_module(f'informa.plugins.{module_name}')
        except ModuleNotFoundError as e:
            logger.error('Plugin not found %s %s', plug, e)
            continue

        if has_rocketry_task(modules[plug]):
            pluginfo = 'Rocketry'
        elif has_fastapi_router(modules[plug]):
            pluginfo = 'FastAPI'

        logger.info('Initialised %s plugin: %s', pluginfo, plug)

    return modules


def has_rocketry_task(module: ModuleType) -> bool:
    for _, func in inspect.getmembers(module, inspect.isfunction):
        if 'load_run_persist' in inspect.getclosurevars(func).globals:
            return True
    return False


def has_fastapi_router(module: ModuleType) -> bool:
    for obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj[1], APIRouter):
            return True
    return False


class Server(uvicorn.Server):
    '''
    Customized uvicorn.Server

    Uvicorn server overrides signals and we need to include Rocketry to the signals.
    '''
    def handle_exit(self, sig: int, frame) -> None:
        app_rocketry.session.shut_down()
        return super().handle_exit(sig, frame)


async def start(host: str, port: int):
    'Run Rocketry and FastAPI'
    server = Server(config=uvicorn.Config(app_fastapi, loop='asyncio', host=host, port=port))

    init_plugins()

    await asyncio.wait([
        asyncio.create_task(server.serve()),
        asyncio.create_task(app_rocketry.serve()),
    ])
