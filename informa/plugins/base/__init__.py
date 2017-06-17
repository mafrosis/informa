from abc import abstractmethod
import collections
import datetime
import json
import logging

import deepdiff
from flask import current_app as app
import memcache
import redis


class InformaBasePlugin(app.celery.Task):
    enabled = False
    run_every = datetime.timedelta(minutes=30)
    sort_output = False
    persist = False

    def __init__(self):
        # create memcache interface
        self.memcache = memcache.Client(
            ['{MEMCACHE_HOST}:{MEMCACHE_PORT}'.format(**app.config)], debug=0
        )

        # init logger for this plugin
        self.logger = logging.getLogger('informa').getChild(str(self))


    def __str__(self):
        # determine the full classpath for this plugin
        return '{}.{}'.format(self.__module__, self.__class__.__name__)


    def run(self, **kwargs):
        data = self.process()
        if data is None:
            raise Exception("Plugin '{}' didn't return anything".format(str(self)))

        # if data has changed since last run, log and store
        if deepdiff.DeepDiff(self.load(), data):
            self.logger.info(data)
            self.store(data)

        return data

    @abstractmethod
    def process(self):
        pass


    def load(self):
        # get from memcache
        data = self.memcache.get(str(self))

        if not data:
            # attempt to load data from cold storage
            redis_ = redis.StrictRedis(app.config['REDIS_HOST'], app.config['REDIS_PORT'])
            obj = None

            try:
                obj = redis_.get(str(self))
            except redis.exceptions.ConnectionError:
                pass

            if obj is None:
                return

            # parse JSON
            data = json.loads(obj.decode('utf8'))

            # add to memcache
            self.memcache.set(str(self), data)

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
                redis_.set(str(self), json.dumps(data))
            except redis.exceptions.ConnectionError:
                pass

        # store into memcache
        self.memcache.set(str(self), data)


def dict_sort(data):
    if type(data) is not dict:
        return data

    for x in data.keys():
        if type(data[x]) is dict:
            data[x] = collections.OrderedDict(sorted(data[x].items()))

    return collections.OrderedDict(sorted(data.items()))
