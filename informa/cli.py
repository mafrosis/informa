import inspect
import os
import logging

import click


from informa.main import init_plugins, start_rocketry
from informa.lib import load_run_persist


logger = logging.getLogger('informa')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.INFO)


@click.group()
@click.option('--debug', is_flag=True, default=False)
def cli(debug):
    # Set DEBUG logging based on ENV or --debug CLI flag
    if debug or os.environ.get('DEBUG'):
        logger.setLevel(logging.DEBUG)


@cli.group('plugin')
def plugin_():
    'Invoke a plugin\'s CLI'

# Load all the plugins at import time
PLUGINS = init_plugins()

# Iterate plugins, looking for Click Groups to include in the CLI
for plugin_module in PLUGINS.values():
    for name, member in inspect.getmembers(plugin_module):
        if isinstance(member, click.core.Group):
            plugin_.add_command(member)


@cli.command
def start():
    'Start the async workers for each plugin'
    start_rocketry()


@cli.command
def list_plugins():
    '''
    List configured plugins
    '''
    for plug in PLUGINS.keys():
        print(plug)


@cli.command
@click.argument('plugin')
def call(plugin: str):
    '''
    Run a single plugin synchronously

    PLUGIN - Name of the plugin to run synchronously on the CLI
    '''
    plug = PLUGINS[plugin]
    load_run_persist(plug.logger, plug.State, plug.PLUGIN_NAME, plug.main)
