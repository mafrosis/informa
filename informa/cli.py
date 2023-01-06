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


@cli.command
def start():
    'Start the async workers for each plugin'
    start_rocketry()


@cli.command
def list_plugins():
    '''
    List configured plugins
    '''
    for plug in init_plugins().keys():
        print(plug)


@cli.command
@click.argument('plugin')
def call(plugin: str):
    '''
    Run a single plugin synchronously

    PLUGIN - Name of the plugin to run synchronously on the CLI
    '''
    plugins = init_plugins()
    plug = plugins[plugin]
    load_run_persist(plug.logger, plug.State, plug.PLUGIN_NAME, plug.main)
