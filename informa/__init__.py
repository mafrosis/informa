import importlib
import yaml

import sqlalchemy

# setup Flask
from flask import Flask
app = Flask(__name__)
app.config.from_pyfile('../config/flask.conf.py')

from .celery import celery
assert celery

# load SQLAlchemy for persisted data
from flask.ext.sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)
from . import schema

# find and import all plugins
app.config['plugins'] = {}

import os
from . import views
assert views


def load_directory(path, enabled_plugins=None):
    # iterate python files
    for root, dirs, files in os.walk(path):
        for filename in files:
            if not filename.startswith('__') and filename.endswith('.py'):
                modname = filename[:-3]

                # skip plugins not defined as enabled
                if enabled_plugins:
                    if modname not in enabled_plugins:
                        print('Inactive plugin: {}'.format(modname))
                        continue

                try:
                    # dynamic import of python modules
                    importlib.import_module(
                        '{}.{}'.format(path.replace('/', '.'), modname)
                    )
                    print('Active plugin: {}'.format(modname))

                except (ImportError, AttributeError) as e:
                    print('Bad plugin: {} ({})'.format(modname, e))


def db_exists(config):
    engine = sqlalchemy.create_engine(config['SQLALCHEMY_DATABASE_URI'])
    return engine.dialect.has_table(engine.connect(), schema.ObjectStore.__tablename__)


# bootstrap DB
if not db_exists(app.config):
    db.create_all()


# load a list of enabled plugins from config
if os.path.exists('plugins.yaml') is False:
    print('No plugins enabled! You must create plugins.yaml')
else:
    try:
        with open('plugins.yaml', 'r') as f:
            plugins = yaml.load(f.read())
    except:
        print('Bad plugins.yaml file')
        plugins = {'enabled': []}

    # store the enabled plugins in global app config
    app.config['plugins'] = {'plugins.{}'.format(p): None for p in plugins['enabled']}

    # load enabled plugins from plugins directory
    load_directory('informa/plugins', enabled_plugins=plugins['enabled'])

# always load plugins defined as part of alerts
load_directory('informa/alerts')
