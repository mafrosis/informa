import importlib
import os
import logging
import time

import click
from rocketry import Rocketry
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


@cli.command
@click.argument('plugin')
@click.option('--timeout', default=3, help='How long to wait for plugin to finish (default: 3s)')
def call(plugin: str, timeout: int):
    '''
    Run a single plugin synchronously

    PLUGIN - Name of the plugin to run
    '''
    app = Rocketry(config={'task_execution': 'main'})

    plug = importlib.import_module(f'informa.plugins.{plugin}')

    @app.task('minutely', execution='main')
    def run():
        plug.fetch_run_publish(plug.logger, plug.State, plug.MQTT_TOPIC, plug.main)

        # Allow short timeout for plugin to run, before exiting all async jobs
        time.sleep(timeout)
        app.session.shut_down()

    logger.debug('Triggering plugin %s', plugin)
    app.run()
