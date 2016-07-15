from abc import abstractmethod
import collections
import datetime
import json
import sys
import traceback

import deepdiff
from flask import current_app as app
import memcache
import redis


class InformaBasePlugin(app.celery.Task):
    enabled = False
    plugin_name = None
    run_every = datetime.timedelta(minutes=30)
    sort_output = False
    persist = False

    def __init__(self):
        # never register periodic tasks for any base plugin
        if 'plugins.base' in self.__module__:
            return

        # set an internal plugin_name
        self.plugin_name = str(self)

        # set the friendly module name as defined in plugins.yaml
        self.friendly_name = self.__module__[7:][self.__module__[7:].index('.')+1:]

        # handle plugins enabled with a definition in plugins.yaml
        if self.friendly_name in app.config['plugins'].keys():
            self.enabled = True

        # add task to the celerybeat schedule
        if self.enabled is True:
            self.app.conf.CELERYBEAT_SCHEDULE[str(self)] = {
                'task': str(self),
                'schedule': self.run_every,
                'args': (),
                'relative': False,
                'kwargs': {},
                'options': {},
            }

        # hide alerts from /get; but only after they're registered to celerybeat
        if 'alerts' in self.__module__:
            self.enabled = False

        # store refs to all plugins in Flask
        app.config['plugins'][self.friendly_name] = {
            'cls': self,
            'enabled': self.enabled,
        }

        # create memcache interface
        self.memcache = memcache.Client(
            ['{MEMCACHE_HOST}:{MEMCACHE_PORT}'.format(**app.config)], debug=0
        )


    def __str__(self):
        # determine the full classpath for this plugin
        return '{}.{}'.format(self.__module__, self.__class__.__name__)


    def run(self, **kwargs):
        data = self.process()
        if data is None:
            raise Exception("Plugin '{}' didn't return anything".format(self.plugin_name))

        # if data has changed since last run, log and store
        if deepdiff.DeepDiff(self.load(), data):
            self.log(data)
            self.store(data)

        return data

    @abstractmethod
    def process(self):
        pass


    def load(self):
        # get from memcache
        data = self.memcache.get(self.plugin_name)

        if not data:
            # attempt to load data from cold storage
            redis_ = redis.StrictRedis(app.config['REDIS_HOST'], app.config['REDIS_PORT'])
            obj = None

            try:
                obj = redis_.get(self.plugin_name)
            except redis.exceptions.ConnectionError:
                pass

            if obj is None:
                return

            # parse JSON
            data = json.loads(obj.decode('utf8'))

            # add to memcache
            self.memcache.set(self.plugin_name, data)

        return data

    def store(self, data):
        # sort the data
        if self.sort_output is True:
            if type(data) is list:
                data = sorted(data)
            elif type(data) is dict:
                data = dict_sort(data)

        # persist in the DB
        if self.persist is True:
            try:
                redis_ = redis.StrictRedis(app.config['REDIS_HOST'], app.config['REDIS_PORT'])
                redis_.set(self.plugin_name, json.dumps(data))
            except redis.exceptions.ConnectionError:
                pass

        # store into memcache
        self.memcache.set(self.plugin_name, data)


    def log(self, msg):
        print('[{}] {}'.format(self.plugin_name, msg))

    def format_excp(self):
        ex_type, ex, tb = sys.exc_info()
        tb = traceback.extract_tb(tb)
        return '{}: {}\n{}'.format(ex.__class__.__name__, ex, tb)


def dict_sort(data):
    if type(data) is not dict:
        return data

    for x in data.keys():
        if type(data[x]) is dict:
            data[x] = collections.OrderedDict(sorted(data[x].items()))

    return collections.OrderedDict(sorted(data.items()))
