from __future__ import absolute_import

import inspect
import importlib
import yaml

# setup Flask
from flask import Flask
app = Flask(__name__)
app.config.from_pyfile('flask.conf.py')

from .celery import celery

# load SQLAlchemy for persisted data
from flask.ext.sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)
from . import schema

# find and import all plugins
app.config['modules'] = {}

import os
from . import views
views.noop()

from .base_plugins import InformBasePlugin


def load_plugin(mod, attr_name, modname):
    # initialise the plugin and store it in global app state
    m = getattr(mod, attr_name)()
    app.config['modules'][modname] = m
    print 'Active plugin: {}'.format(modname)


def load_directory(path, enabled_plugins=None):
    # iterate python files
    for root, dirs, files in os.walk(path):
        for filename in files:
            if not filename.startswith('__') and filename.endswith('.py'):
                modname = filename[:-3]

                # skip plugins not defined as enabled
                if enabled_plugins:
                    if modname not in enabled_plugins:
                        print 'Inactive plugin: {}'.format(modname)
                        continue

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


# load a list of enabled plugins from config
if os.path.exists('plugins.yaml') is False:
    print 'No plugins enabled! You must create plugins.yaml'
else:
    try:
        with open('plugins.yaml', 'r') as f:
            plugins = yaml.load(f.read())
    except:
        print 'Bad plugins.yaml file'
        plugins = {'enabled': []}

    # load plugins from plugins directory
    load_directory('inform/plugins', enabled_plugins=plugins['enabled'])

# always load plugins defined as part of alerts
load_directory('inform/alerts')


if __name__ == '__main__':
    app.run()
