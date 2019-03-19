from abc import abstractmethod
import collections
import datetime
import json
import logging

import deepdiff
from flask import current_app as app
import redis


# classmethod __str__
class Meta(type):
    def __repr__(self):
        return '{}.{}'.format(self.__module__, self.__name__)


class InformaBasePlugin(app.celery.Task, metaclass=Meta):
    run_every = datetime.timedelta(minutes=30)
    sort_output = False
    celery_disable = False
    force = False

    def __init__(self):
        self.redis_ = redis.StrictRedis(app.config['REDIS_HOST'], app.config['REDIS_PORT'])

        # create logger for this plugin
        self.logger = logging.getLogger('informa').getChild(str(self))
        # display plugin name in logs
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter('%(levelname)s {} %(message)s'.format(self.__name__)))
        self.logger.addHandler(sh)

    def __repr__(self):
        return str(self.__class__)

    @classmethod
    def on_bound(cls, app):
        # log plugin active
        logger = logging.getLogger('informa').getChild(str(cls))
        logger.info('polling in celery')


    def run(self, **kwargs):
        """
        Async run method called on celery worker
        """
        self.logger.debug('Running {}'.format(str(self)))

        data = self.process(kwargs['data'] if 'data' in kwargs else {})
        if data is None:
            raise Exception("Plugin '{}' didn't return anything".format(str(self)))

        # if data has changed since last run, log and store
        if deepdiff.DeepDiff(self.load(), data):
            self.logger.info(data)
            self._store(data)

        return data

    @abstractmethod
    def process(self):
        """
        Method must be overriden in child-class to implement plugin functionality
        """
        pass

    def get(self, force=False):
        """
        Retrieve data stored for this plugin
        """
        data = self.load()

        # cast strings as JSON
        if type(data) is str:
            data = json.loads(data)

        # set force flag on plugin object
        self.force = force

        # refresh data if none is present
        if not data or force is True:
            data = self.run(data=data)

        return data


    def load(self):
        # attempt to load data from cold storage
        obj = None

        try:
            obj = self.redis_.get(str(self))
        except redis.exceptions.ConnectionError:
            pass

        if obj is None:
            return

        return obj.decode('utf8')

    def _store(self, data):
        # sort the data
        if self.sort_output is True:
            if type(data) is list:
                data = sorted(data)
            elif type(data) is dict:
                data = dict_sort(data)

        try:
            self.redis_.set(str(self), json.dumps(data))
        except redis.exceptions.ConnectionError:
            pass


def dict_sort(data):
    if type(data) is not dict:
        return data

    for x in data.keys():
        if type(data[x]) is dict:
            data[x] = collections.OrderedDict(sorted(data[x].items()))

    return collections.OrderedDict(sorted(data.items()))
