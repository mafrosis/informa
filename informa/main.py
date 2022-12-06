import importlib
import os
import logging

import yaml

from informa.lib import app


logger = logging.getLogger('informa')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.INFO)

if os.environ.get('DEBUG'):
    logger.setLevel(logging.DEBUG)


def main():
    init_plugins()
    app.run()


def init_plugins():
    # Load active plugins from YAML config
    with open('plugins.yaml', encoding='utf8') as f:
        plugins = yaml.safe_load(f)['plugins']

    # Iterate loaded plugins
    for plug in plugins:
        # Dynamic import to register rocketry tasks
        importlib.import_module(f'informa.plugins.{plug}')
