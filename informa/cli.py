import asyncio
import logging
import os

import arrow
import click
import requests

from informa import app
from informa.lib import CliOpts, pretty
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
@click.option('--server', help='Connect to an Informa at hostname', default='https://informa.mafro.net/', type=str)
@click.pass_context
def cli(ctx, debug: bool, server: str):
    # Set DEBUG logging based on ENV or --debug CLI flag
    if debug or os.environ.get('DEBUG'):
        logger.setLevel(logging.DEBUG)

    ctx.obj = CliOpts(server)


@cli.group('plugin')
@click.pass_obj
def plugin_(opts: CliOpts):
    'Invoke a plugin\'s CLI'

    for plugin in app.plugins.values():
        # Ensure the --server param is available within each InformaPlugin
        plugin.informa_hostname = opts.server

        # Set every plugin's CLI to accept their InformaPlugin object via context
        plugin.module.cli.context_settings = {'obj': plugin}


# Load all the plugins at import time, to populate the CLI
app.init()
app.configure_cli(plugin_)


@cli.command
@click.option('--host', help='Start Informa on host', default='127.0.0.1', type=str)
@click.option('--port', help='Start Informa on port', default=3000, type=int)
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


def verify_plugin_or_raise(plugin_name: str):
    if not plugin_name.startswith('informa.plugins.'):
        plugin_name = f"informa.plugins.{plugin_name.replace('-', '_')}"
    else:
        plugin_name = plugin_name.replace('-', '_')

    if plugin_name not in app.plugins:
        raise click.ClickException(f'Invalid plugin: {plugin_name}')
    return plugin_name


@admin_.command
@click.argument('plugin_name')
@click.option('--persist', is_flag=True, default=False)
@click.pass_obj
def enable(opts: CliOpts, plugin_name: str, persist: bool):
    'Enable a plugin'
    plugin_name = verify_plugin_or_raise(plugin_name)

    resp: requests.Response

    try:
        resp = requests.post(f'{opts.server}/admin/plugins/{plugin_name}', timeout=1, params={'persist': persist})
        resp.raise_for_status()

        print(f'Plugin {plugin_name} enabled')

    except requests.exceptions.ConnectionError as e:
        raise click.ClickException('It appears that Informa is currently down') from e
    except requests.RequestException as e:
        if 'detail' in resp.json():
            raise click.ClickException(resp.json()['detail']) from e
        raise click.ClickException('Failed to enable plugin') from e


@admin_.command
@click.argument('plugin_name')
@click.option('--persist', is_flag=True, default=False)
@click.pass_obj
def disable(opts: CliOpts, plugin_name: str, persist: bool):
    'Disable a plugin'
    plugin_name = verify_plugin_or_raise(plugin_name)

    resp: requests.Response

    try:
        resp = requests.delete(f'{opts.server}/admin/plugins/{plugin_name}', timeout=1, params={'persist': persist})
        resp.raise_for_status()

        print(f'Plugin {plugin_name} disabled')

    except requests.exceptions.ConnectionError as e:
        raise click.ClickException('It appears that Informa is currently down') from e
    except requests.RequestException as e:
        if 'detail' in resp.json():
            raise click.ClickException(resp.json()['detail']) from e
        raise click.ClickException('Failed to disable plugin') from e


@admin_.command('list')
@click.pass_obj
def list_plugins(opts: CliOpts):
    'List configured plugins by fetching from API'
    try:
        resp = requests.get(f'{opts.server}/admin/plugins', timeout=1)
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
