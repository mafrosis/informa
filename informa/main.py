import importlib
import logging

import yaml

from informa.lib import app


logger = logging.getLogger('informa')


def start_rocketry():
    init_plugins()
    app.run()


def init_plugins():
    # Load active plugins from YAML config
    with open('plugins.yaml', encoding='utf8') as f:
        plugins = yaml.safe_load(f)['plugins']

    for plug in plugins:
        # Dynamic import to register rocketry tasks
        logger.debug('Initialising plugin %s', plug)
        importlib.import_module(f'informa.plugins.{plug}')
