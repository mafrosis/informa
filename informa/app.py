import inspect
import importlib
import logging
import os
import sys
import yaml

from celery import Celery, signals
from flask import Flask
from flask_ask import Ask

from .exceptions import DisabledPlugin, InactivePlugin, NotAPlugin
from .lib.json import init_json
from .views import base

logger = logging.getLogger('informa')


def create_app():
    # setup Flask
    app = Flask(__name__)
    app.config.from_pyfile('../config/flask.conf.py')

    init_json(app)

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
    app.register_blueprint(base.bp)

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
    all_plugins = app.config['plugins']['enabled'] + app.config['plugins']['disabled']

    for filename in os.listdir(path):
        if filename == '__pycache__':
            continue

        try:
            # determine if file/dir is useable python module
            modname = get_py_module(os.path.join(path, filename))

            # skip inactive plugins
            plugin_name = os.path.splitext(modname)[1][1:]
            if plugin_name not in all_plugins:
                raise DisabledPlugin(modname)

            is_plugin_active = True
            if plugin_name in app.config['plugins']['disabled']:
                is_plugin_active = False

        except NotAPlugin:
            continue
        except DisabledPlugin as e:
            continue

        load_plugin(app, modname, is_plugin_active)


def load_plugin(app, modname, is_plugin_active=False):
    """
    Load a single plugin and register its celery task
    """
    try:
        # dynamic import of plugins
        mod = importlib.import_module(modname)

        plugin_name = os.path.splitext(modname)[1][1:]

        # late import cause celery
        from .plugins.base import InformaBasePlugin

        # get InformaBasePlugin class from module
        PluginClass = next(iter([
            v for v in mod.__dict__.values()
            if inspect.isclass(v)
                and issubclass(v, InformaBasePlugin)
                and v != InformaBasePlugin
        ]))

        # instantiate task
        cls = PluginClass()

        # only active in plugins.yml, and register as periodic
        if is_plugin_active:
            task = app.celery.register_task(cls)
            app.celery.add_periodic_task(task.run_every, task.s(), name=task.__name__)

        # store refs to all plugins in Flask.config for CLI access
        if not 'cls' in app.config:
            app.config['cls'] = {}

        app.config['cls'][plugin_name] = cls

        logger.info('{} loaded'.format(plugin_name))

    except StopIteration:
        # no valid plugin found in module
        logger.error('No plugin in module: {}'.format(modname))

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
