from abc import abstractmethod
import collections
import datetime
import json
from socket import socket
import sys
import time
import traceback

from celery import Task

from ... import app, db
from ...celery import celery
from ...schema import ObjectStore
from ...memcache_wrapper import cache


class InformaBasePlugin(Task):
    enabled = False
    plugin_name = None
    run_every = datetime.timedelta(minutes=30)
    sort_output = False

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
            celery.conf.CELERYBEAT_SCHEDULE[str(self)] = {
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

    def __str__(self):
        # determine the full classpath for this plugin
        return '{}.{}'.format(self.__module__, self.__class__.__name__)


    def run(self, **kwargs):
        data = self.process()
        if data is None:
            raise Exception("Plugin '{}' didn't return anything".format(self.plugin_name))

        self.store(data)
        return data

    @abstractmethod
    def process(self):
        pass


    def load(self, persistent=False):
        if persistent is True:
            return self._load_persistent()

        return cache.get(self.plugin_name)

    def store(self, data, persistent=False):
        # sort the data
        if self.sort_output is True:
            if type(data) is list:
                data = sorted(data)
            elif type(data) is dict:
                data = dict_sort(data)

        # persist in the DB
        if persistent is True:
            self._store_persistent(data)

        # store into memcache
        cache.set(self.plugin_name, data)

    def _load_persistent(self):
        # load persisted data from DB
        obj = ObjectStore.query.filter_by(plugin_name=self.plugin_name).first()
        if obj is None:
            return None
        return json.loads(obj.data)

    def _store_persistent(self, data):
        # check object exists; create or update
        obj = ObjectStore.query.filter_by(plugin_name=self.plugin_name).first()
        if obj is None:
            obj = ObjectStore(self.plugin_name, data=json.dumps(data))
        else:
            obj.data = json.dumps(data)

        # store persisted data in DB
        db.session.add(obj)
        db.session.commit()


    def log_to_graphite(self, metric, value=0):
        try:
            sock = socket()
            sock.connect((app.config['GRAPHITE_HOST'], app.config['GRAPHITE_PORT']))
            sock.sendall('{} {} {}\n'.format(metric, value, int(time.time())))
            self.log('Logged to Graphite {} {}'.format(metric, value))

        except KeyError:
            self.log('Graphite server not configured')
        except IOError:
            self.log('Error logging to Graphite')
        finally:
            sock.close()

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
