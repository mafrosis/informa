import inspect
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

logger = logging.getLogger('informa')


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
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    app.celery.Task = ContextTask

    # register views
    app.register_blueprint(base)

    # import plugins, with a Flask context
    with app.app_context():
        find_plugins(app)

    return app


@signals.setup_logging.connect
def setup_celery_logging(**kwargs):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s %(levelname)s/%(processName)s] %(name)s %(message)s'))
    logger.addHandler(handler)


def find_plugins(app):
    """
    Load plugins.yaml into flask_app.config and load plugin directories
    """
    if os.path.exists('plugins.yaml') is False:
        logger.critical('No plugins enabled! You must create plugins.yaml')
        return

    try:
        with open('plugins.yaml', 'r') as f:
            app.config['plugins'] = yaml.load(f.read())
    except:
        logger.critical('Bad plugins.yaml file')
        sys.exit(44)

    # load enabled plugins from plugins directory
    load_directory(app, 'informa/plugins')

    # always load plugins defined as part of alerts
    load_directory(app, 'informa/plugins/base/alerts')


def load_directory(app, path):
    """
    Load all Informa plugins from path
    """
    for filename in os.listdir(path):
        if filename == '__pycache__':
            continue

        try:
            # determine if file/dir is useable python module
            modname = get_py_module(os.path.join(path, filename))

            # skip inactive plugins
            plugin_name = os.path.splitext(modname)[1][1:]
            if plugin_name not in app.config['plugins']['enabled']:
                raise InactivePlugin(modname)

        except NotAPlugin:
            continue
        except InactivePlugin as e:
            continue

        load_plugin(app, modname)


def load_plugin(app, modname):
    """
    Load a single plugin and register its celery task
    """
    try:
        # dynamic import of python modules
        mod = importlib.import_module(modname)

        # get class from module
        PluginClass = next(iter([
            v for v in mod.__dict__.values()
            if inspect.isclass(v)
                and 'informa.plugins' in v.__module__
                and 'base' not in v.__module__
        ]))

        # instantiate task and register as periodic
        task = app.celery.register_task(PluginClass())
        app.celery.add_periodic_task(task.run_every, task.s(), name=task.__name__)

        plugin_name = os.path.splitext(modname)[1][1:]

        # store refs to all plugins in Flask.config for CLI access
        if not 'cls' in app.config:
            app.config['cls'] = {}
        app.config['cls'][plugin_name] = task

    except StopIteration:
        # no valid plugin found in module
        pass
    except (ImportError, AttributeError) as e:
        logger.error('Bad plugin: {} ({})'.format(modname, e))


def get_py_module(path):
    """
    Find an informa plugin module in path
    """
    if os.path.basename(path).startswith('__'):
        raise NotAPlugin

    if os.path.isfile(path) and path.endswith('.py'):
        modname = os.path.basename(path)[:-3]
    elif os.path.isdir(path) and not os.path.basename(path) == 'base' and '__init__.py' in os.listdir(path):
        modname = os.path.basename(path)
    else:
        raise NotAPlugin

    return '{}.{}'.format(os.path.dirname(path).replace('/', '.'), modname)
