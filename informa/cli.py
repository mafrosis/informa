import asyncio
import logging
import os

import click

from informa import app
from informa.main import start as start_app

logger = logging.getLogger('informa')
sh = logging.StreamHandler()
logger.addHandler(sh)
sh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.setLevel(logging.INFO)
if os.environ.get('DEBUG'):
    logger.setLevel(logging.DEBUG)


@click.group()
@click.option('--debug', is_flag=True, default=False)
def cli(debug):
    # Set DEBUG logging based on ENV or --debug CLI flag
    if debug or os.environ.get('DEBUG'):
        logger.setLevel(logging.DEBUG)


@cli.group('plugin')
def plugin_():
    'Invoke a plugin\'s CLI'


# Load all the plugins at import time, to populate the CLI
app.init()
app.configure_cli(plugin_)


@cli.command
@click.option('--host', help='Bind FastAPI server to hostname', default='127.0.0.1', type=str)
@click.option('--port', help='Bind FastAPI server to port', default=3000, type=int)
@click.option('--plugins', help='Start informa with a subset of plugins enabled (comma-separated)', default=None)
def start(host: str, port: int, plugins: str | None):
    'Start the async workers for each plugin, and the API server'
    if plugins:
        plugins = plugins.replace('-', '_').split(',')

        for i, pn in enumerate(plugins):
            if not pn.startswith('informa.plugins.'):
                plugin_name = f'informa.plugins.{pn}'
                plugins[i] = plugin_name

            if plugin_name not in app.plugins:
                logger.error('Plugin %s not found', plugin_name)
                return

    asyncio.run(start_app(host, port, plugins))


@cli.command
def list_plugins():
    '''
    List configured plugins
    '''
    for plugin_name, plugin in app.plugins.items():
        print(plugin_name)
        for task in plugin.tasks:
            if isinstance(task.condition, str):
                print(f'-> T: {task.func.__name__}, {task.condition}')
            else:
                print(f'-> T: {task.func.__name__}, <condition>')
