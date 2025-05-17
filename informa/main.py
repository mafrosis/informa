import asyncio
import datetime
import importlib
import inspect
import logging
import pathlib
from typing import Callable

import click
import dataclasses_json
import uvicorn
from fastapi import APIRouter, FastAPI
from rocketry import Rocketry
from zoneinfo import ZoneInfo

from informa.lib import F, InformaPlugin, InformaTask
from informa.lib.plugin import plugin_last_run, plugin_run_now

logger = logging.getLogger('informa')


# Setup dataclasses_json to serialise date & datetime as ISO8601
dataclasses_json.cfg.global_config.encoders[datetime.date] = datetime.date.isoformat
dataclasses_json.cfg.global_config.decoders[datetime.date] = datetime.date.fromisoformat
dataclasses_json.cfg.global_config.encoders[datetime.datetime] = datetime.datetime.isoformat
dataclasses_json.cfg.global_config.decoders[datetime.datetime] = datetime.datetime.fromisoformat


class Informa:
    def __init__(self) -> None:
        self.plugins: dict[str, InformaPlugin] = {}
        self.rocketry = Rocketry(
            config={
                'execution': 'thread',
                'timezone': ZoneInfo('Australia/Melbourne'),
                'cycle_sleep': 10,
            }
        )
        self.fastapi = FastAPI()

    def init(self):  # noqa: PLR6301
        plugin_path = pathlib.Path(inspect.getfile(inspect.currentframe())).parent / 'plugins'

        for plug in plugin_path.glob('*.py'):
            # Convert dashes into underscores for python imports
            module_name = plug.stem.replace('-', '_')

            try:
                # Dynamic import
                importlib.import_module(f'informa.plugins.{module_name}')

            except ModuleNotFoundError as e:
                logger.error('Plugin "%s" not loaded: %s', plug.name, e)
                continue

    def configure_cli(self, informa_cli: click.core.Group):
        for plugin in self.plugins.values():
            if plugin.cli is None:
                logger.debug('No CLI defined on plugin %s', plugin.name)
                continue

            # Setup plugin CLI subcommand
            informa_cli.add_command(plugin.cli)
            # Add common commands to plugin CLI
            plugin.module.cli.context_settings = {'obj': plugin}
            plugin.module.cli.add_command(plugin_last_run)
            plugin.module.cli.add_command(plugin_run_now)

    def task(self, condition: str) -> Callable[[F], F]:
        '''
        Decorator to register a plugin function as a task. This method will instantiate an
        InformaPlugin if one doesn't yet exist for the plugin.

        Args:
            condition:  The condition string for the task (eg. `every 5 mins`)
        '''

        def decorator(func: F) -> F:
            try:
                plugin = self.plugins[func.__module__]
            except KeyError:
                # Instantiate an InformaPlugin
                plugin = InformaPlugin(inspect.getmodule(func))
                self.plugins[func.__module__] = plugin

            plugin.tasks.append(InformaTask(func, condition))
            return func

        return decorator

    def api(self, router: APIRouter) -> Callable[[F], F]:
        '''
        Decorator to register a plugin function as a task. This method will instantiate an
        InformaPlugin if one doesn't yet exist for the plugin.

        Args:
            path:  The fastapi.APIRouter object used for this API
        '''

        def decorator(func: F) -> F:
            try:
                plugin = self.plugins[func.__module__]
            except KeyError:
                # Instantiate an InformaPlugin
                plugin = InformaPlugin(inspect.getmodule(func))
                self.plugins[func.__module__] = plugin

            plugin.api = router
            return func

        return decorator


app = Informa()


class Server(uvicorn.Server):
    '''
    Customized uvicorn.Server. Rocketry needs to shutdown when Uvicorn shuts down.
    '''

    def handle_exit(self, sig: int, frame) -> None:
        app.rocketry.session.shut_down()
        return super().handle_exit(sig, frame)


async def start(host: str, port: int):
    'Run Rocketry and FastAPI'
    server = Server(config=uvicorn.Config(app.fastapi, loop='asyncio', host=host, port=port))

    for plugin_name, plugin in app.plugins.items():
        # Register Rocketry tasks
        for task in plugin.tasks:
            logger.info('Started task %s from %s', task.func.__name__, plugin_name)
            app.rocketry.session.create_task(
                func=task.func,
                start_cond=task.condition,
                name=f'{plugin_name}.{task.func.__name__}',
            )

        # Register FastAPI routers
        if plugin.api:
            logger.info('Added FastAPI router %s from %s', plugin.api.prefix, plugin_name)
            app.fastapi.include_router(plugin.api)

    await asyncio.wait([
        asyncio.create_task(server.serve()),
        asyncio.create_task(app.rocketry.serve()),
    ])
