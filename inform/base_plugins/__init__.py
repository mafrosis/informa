from __future__ import absolute_import

from abc import abstractmethod
import collections
import datetime
from socket import socket
import sys
import time
import traceback

from celery.task import PeriodicTask

from .. import app
from ..memcache_wrapper import cache


class InformBasePlugin(PeriodicTask):
    enabled = True
    plugin_name = None
    run_every = datetime.timedelta(minutes=30)
    sort_output = False

    def __init__(self):
        # set an internal plugin_name
        self.plugin_name = str(self)

    def __str__(self):
        # determine the full classpath for this plugin
        return '{}.{}'.format(self.__module__, self.__class__.__name__)


    def run(self, **kwargs):
        self.log('Running plugin')
        data = self.process()
        if data is None:
            raise Exception("Plugin '{}' didn't return anything".format(self.plugin_name))

        self.store(data)
        return data

    def load(self):
        return cache.get(self.plugin_name)

    def store(self, data):
        # sort the data
        if self.sort_output is True:
            if type(data) is list:
                data = sorted(data)
            elif type(data) is dict:
                data = dict_sort(data)

        # store into memcache
        cache.set(self.plugin_name, data)


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
        print '[{}] {}'.format(self.plugin_name, msg)

    def format_excp(self):
        ex_type, ex, tb = sys.exc_info()
        tb = traceback.extract_tb(tb)
        return '{}: {}\n{}'.format(ex.__class__.__name__, ex, tb)


    @abstractmethod
    def process(self):
        pass


def dict_sort(data):
    if type(data) is not dict:
        return data

    for x in data.keys():
        if type(data[x]) is dict:
            data[x] = collections.OrderedDict(sorted(data[x].items()))

    return collections.OrderedDict(sorted(data.items()))
