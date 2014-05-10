from __future__ import absolute_import

import inspect
import importlib

# setup Flask
from flask import Flask
app = Flask(__name__)
app.config.from_pyfile('flask.conf.py')

from .celery import celery

# find and import all plugins
app.config['modules'] = {}

import os
from . import views
views.noop()

from .base_plugins import InformBasePlugin


def load_plugin(mod, attr_name, modname):
    # check if the plugin class is marked as enabled
    cls = getattr(mod, attr_name)
    if getattr(cls, 'enabled', True):
        # initialise the plugin and store it in global app state
        m = cls()
        app.config['modules'][modname] = m
        print 'Active plugin: {}'.format(modname)
    else:
        print 'Inactive plugin: {}'.format(modname)


def load_directory(path):
    # iterate python files
    for root, dirs, files in os.walk(path):
        for filename in files:
            if not filename.startswith('__') and filename.endswith('.py'):
                modname = filename[:-3]

                try:
                    # dynamic import of python modules
                    mod = importlib.import_module(
                        '{}.{}'.format(path.replace('/', '.'), modname)
                    )

                    # iterate module attributes
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        # only load subclasses of InformBase plugin ..
                        if inspect.isclass(attr) and issubclass(attr, InformBasePlugin):
                            # .. that were defined in the python module
                            if inspect.getmodule(attr) is mod:
                                load_plugin(mod, attr_name, modname)

                except (ImportError, AttributeError) as e:
                    print 'Bad plugin: {} ({})'.format(modname, e)


# load plugins from plugins directory
load_directory('inform/plugins')
load_directory('inform/alerts')


if __name__ == '__main__':
    app.run()
