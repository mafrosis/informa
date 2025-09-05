import asyncio
import logging
import os

import arrow
import click
import requests

from informa import app
from informa.lib import pretty
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


@cli.group('admin')
def admin_():
    'Plugin management commands'

@admin_.command('list')
@click.option('--host', help='Connect to Informa at hostname', default='127.0.0.1', type=str)
@click.option('--port', help='Connect to Informa on port', default=3000, type=int)
def list_plugins(host: str, port: int):
    '''
    List configured plugins by fetching from API
    '''
    try:
        resp = requests.get(f'http://{host}:{port}/admin/plugins', timeout=1)
        resp.raise_for_status()

    except requests.exceptions.ConnectionError as e:
        raise click.ClickException('It appears that Informa is currently down') from e
    except requests.RequestException as e:
        raise click.ClickException('Failed to fetch plugins') from e

    table_data = [
        (
            plugin['name'],
            arrow.get(plugin['last_run']).humanize() if plugin['last_run'] else 'Never',
            plugin['last_count'] if plugin['last_count'] is not None else 'n/a',
            'Enabled' if plugin['enabled'] else 'Disabled',
            '\n'.join(plugin['tasks']),
        )
        for plugin in resp.json()
    ]

    pretty.table(table_data, columns=['name', 'last_run', 'last_count', 'status', 'tasks'])
