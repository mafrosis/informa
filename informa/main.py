import functools
import importlib
import logging
from types import ModuleType
from typing import Dict

import yaml

from informa.lib import app


logger = logging.getLogger('informa')


def start_rocketry():
    init_plugins()
    app.run()


@functools.lru_cache()
def init_plugins() -> Dict[str, ModuleType]:
    # Load active plugins from YAML config
    with open('plugins.yaml', encoding='utf8') as f:
        plugins = yaml.safe_load(f)['plugins']

    modules = {}

    for plug in plugins:
        # Dynamic import to register rocketry tasks
        logger.debug('Initialising plugin %s', plug)
        modules[plug] = importlib.import_module(f'informa.plugins.{plug}')

    return modules
