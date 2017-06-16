import importlib
import logging
import os
import sys
import yaml

from celery import Celery, signals
from flask import Flask
from flask_ask import Ask

from .views import base
from .exceptions import InactivePlugin, NotAPlugin


def create_app():
    # setup Flask
    app = Flask(__name__)
    app.config.from_pyfile('../config/flask.conf.py')

    # init Flask-Ask
    app.ask = Ask(app, '/alexa')

    # find and import all plugins
    app.config['plugins'] = {}

    # init Celery
    app.celery = Celery(broker=app.config['BROKER_URL'])
    app.celery.config_from_object(app.config)

    # http://flask.pocoo.org/docs/0.10/patterns/celery
    TaskBase = app.celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    app.celery.Task = ContextTask

    # register views
    app.register_blueprint(base)

    # setup application logger before tasks are imported
    setup_logger()

    # import plugins, with a Flask context
    with app.app_context():
        find_plugins(app)

    return app


def setup_logger():
    # Flask app logging stays default, configure Python logging for celery
    logger = logging.getLogger('informa')
    logger.level = logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s %(levelname)s/%(processName)s] %(name)s %(message)s'))
    logger.addHandler(handler)

# completely disable celery logging
@signals.setup_logging.connect
def setup_celery_logging(**kwargs):
    pass


def find_plugins(app):
    # load a list of enabled plugins from config
    if os.path.exists('plugins.yaml') is False:
        sys.stderr.write('No plugins enabled! You must create plugins.yaml\n')
    else:
        try:
            with open('plugins.yaml', 'r') as f:
                plugins = yaml.load(f.read())
        except:
            sys.stderr.write('Bad plugins.yaml file\n')
            plugins = {'enabled': []}

        # override disabled for plugin called via CLI load command
        plugins['enabled'].append(sys.argv[-1])

        # store the enabled plugins in global app config
        app.config['plugins'] = {'plugins.{}'.format(p): None for p in plugins['enabled']}

        # load enabled plugins from plugins directory
        load_directory('informa/plugins', enabled_plugins=plugins['enabled'])

        # remove bullshit plugins created from sys.argv[-1]
        app.config['plugins'] = {k:v for k,v in app.config['plugins'].items() if v is not None}

    # always load plugins defined as part of alerts
    load_directory('informa/plugins/base/alerts')


def load_directory(path, enabled_plugins=None):
    for filename in os.listdir(path):
        try:
            # determine if file/dir is useable python module
            modname = get_py_module(
                os.path.join(path, filename),
                enabled_plugins=enabled_plugins
            )
        except NotAPlugin as e:
            continue
        except InactivePlugin as e:
            sys.stderr.write('Inactive plugin: {}\n'.format(e))
            continue

        try:
            # dynamic import of python modules
            importlib.import_module(modname)
            sys.stderr.write('Active plugin: {}\n'.format(modname))

        except (ImportError, AttributeError) as e:
            sys.stderr.write('Bad plugin: {} ({})\n'.format(modname, e))


def get_py_module(path, enabled_plugins=None):
    if os.path.basename(path).startswith('__'):
        raise NotAPlugin

    if os.path.isfile(path) and path.endswith('.py'):
        modname = os.path.basename(path)[:-3]
    elif os.path.isdir(path) and not os.path.basename(path) == 'base' and '__init__.py' in os.listdir(path):
        modname = os.path.basename(path)
    else:
        raise NotAPlugin

    # skip plugins not defined as enabled
    if enabled_plugins:
        if modname not in enabled_plugins:
            raise InactivePlugin(modname)

    return '{}.{}'.format(os.path.dirname(path).replace('/', '.'), modname)
