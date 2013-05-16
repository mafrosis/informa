from celery.task import PeriodicTask
from datetime import timedelta

from lib.memcache_wrapper import cache

from abc import abstractmethod


class InformBasePlugin(PeriodicTask):
    run_every = timedelta(minutes=30)

    def run(self, **kwargs):
        self.process()

    def load(self, key, default=None):
        data = cache.get(key)
        if data is None:
            return default
        return data

    def store(self, key, value):
        if key.startswith("inform.plugins."):
            key = key[15:]
        cache.set(key, value)

    @abstractmethod
    def process(self):
        pass
