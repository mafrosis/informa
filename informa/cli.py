import os
import logging

import click
import yaml


from informa.main import start_rocketry


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
    with open('plugins.yaml', encoding='utf8') as f:
        plugins = yaml.safe_load(f)['plugins']

    for plug in plugins:
        print(plug)
