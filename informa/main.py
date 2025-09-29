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

from informa.exceptions import PluginAlreadyDisabled, PluginAlreadyEnabled
from informa.lib.config import AppConfig, load_app_config, save_app_config
from informa.lib.plugin import F, InformaPlugin, InformaTask, plugin_last_run, plugin_run_now

logger = logging.getLogger('informa')


# Setup dataclasses_json to serialise date & datetime as ISO8601
dataclasses_json.cfg.global_config.encoders[datetime.date] = datetime.date.isoformat
dataclasses_json.cfg.global_config.decoders[datetime.date] = datetime.date.fromisoformat
dataclasses_json.cfg.global_config.encoders[datetime.datetime] = datetime.datetime.isoformat
dataclasses_json.cfg.global_config.decoders[datetime.datetime] = datetime.datetime.fromisoformat


class Informa:
    plugins: dict[str, InformaPlugin]
    rocketry: Rocketry
    fastapi: FastAPI
    config: AppConfig

    def __init__(self):
        self.plugins = {}
        self.rocketry = Rocketry(
            config={
                'execution': 'async',
                'timezone': ZoneInfo('Australia/Melbourne'),
                'cycle_sleep': 10,
            }
        )
        self.fastapi = FastAPI()
        self.config = load_app_config()

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

            # CLI commands are marshalled to a remote Informa server via HTTP.
            # This code wraps each CLI function callback, and modifies the Click handler code to
            # point to a HTTP dispatcher.

            for name, cmd in plugin.cli.commands.items():
                # Track the underlying function for calling during the HTTP handler
                plugin.cli.commands[name].inner_callback = cmd.callback

                # Wrap each CLI command with HTTP request dispatcher
                plugin.cli.commands[name] = plugin.wrap_cli(cmd)

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


    def enable_plugin(self, plugin_name: str, persist: bool = False):
        'Enable plugin by adding its tasks and API router'
        plugin = self.plugins[plugin_name]
        if plugin.enabled is True:
            raise PluginAlreadyEnabled(plugin_name)
        plugin.enabled = True

        # Register Rocketry tasks
        for task in plugin.tasks:
            task_name = f'{plugin_name}.{task.func.__name__}'

            self.rocketry.session.create_task(
                func=task.func,
                start_cond=task.condition,
                name=task_name,
                parameters={'plugin': plugin},
            )
            logger.info('Started task %s', task_name)

        if plugin.api:
            # Register FastAPI routers
            self.fastapi.include_router(plugin.api)
            logger.info('Added FastAPI router %s from %s', plugin.api.prefix, plugin_name)

        if plugin.cli:
            # Create a router to serve the function behind each CLI command as an API endpoint
            plugin_cli_router = APIRouter(prefix=f'/cli/{plugin_name}')
            logger.debug('Added FastAPI router %s', plugin_cli_router.prefix)
            # Add an API route for every CLI command
            for name, cmd in plugin.cli.commands.items():
                plugin_cli_router.add_api_route(f'/{name}', plugin.cli_handler(cmd), methods=['POST'])
            self.fastapi.include_router(plugin_cli_router)

        if persist:
            # Persist plugin enabled state to disk for next restart
            config = load_app_config()
            if plugin_name in config.disabled_plugins:
                config.disabled_plugins.remove(plugin_name)
                save_app_config(config)

    def disable_plugin(self, plugin_name: str, persist: bool = False):
        'Disable plugin by removing its tasks and API router'
        plugin = self.plugins[plugin_name]
        if plugin.enabled is False:
            raise PluginAlreadyDisabled(plugin_name)
        plugin.enabled = False

        # Remove tasks from rocketry scheduler
        for task in plugin.tasks:
            try:
                task_name = f'{plugin_name}.{task.func.__name__}'
                self.rocketry.session.remove_task(task_name)
                logger.info('Removed task %s', task_name)
            except KeyError:
                pass

        if plugin.api:
            # Remove API router if present
            for i, route in enumerate(self.fastapi.routes):
                if route.path.startswith(plugin.api.prefix):
                    self.fastapi.routes.pop(i)
                    logger.info('Removed router %s from %s', plugin.api.prefix, plugin_name)

        if persist:
            # Persist plugin disabled state to disk for next restart
            config = load_app_config()
            if plugin_name not in config.disabled_plugins:
                config.disabled_plugins.add(plugin_name)
                save_app_config(config)


app = Informa()


class Server(uvicorn.Server):
    '''
    Customized uvicorn.Server. Rocketry needs to shutdown when Uvicorn shuts down.
    '''

    def handle_exit(self, sig: int, frame) -> None:
        app.rocketry.session.shut_down()
        return super().handle_exit(sig, frame)


async def start(host: str, port: int, only_run_plugins: list[str] | None = None):
    'Run Rocketry and FastAPI'
    server = Server(config=uvicorn.Config(app.fastapi, loop='asyncio', host=host, port=port))

    for plugin_name, plugin in app.plugins.items():
        if only_run_plugins and plugin.name not in only_run_plugins:
            # Mark plugin as disabled in-memory; and do not enable
            plugin.enabled = False
            continue

        if plugin.name in app.config.disabled_plugins:
            # Plugin is disabled in config; do not enable
            logger.info('Plugin %s is disabled, not starting tasks or API', plugin.name)
            plugin.enabled = False
            continue

        # Activate plugin
        app.enable_plugin(plugin_name)

    # Include admin routes
    from informa.admin import router as admin_api  # noqa: PLC0415
    app.fastapi.include_router(admin_api)

    await asyncio.wait([
        asyncio.create_task(server.serve()),
        asyncio.create_task(app.rocketry.serve()),
    ])
