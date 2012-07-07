from celery.task import PeriodicTask
from datetime import timedelta

from lib.memcache_wrapper import cache

from abc import abstractmethod


class InformBasePlugin(PeriodicTask):
    run_every = timedelta(minutes=30)

    def run(self, **kwargs):
        self.process()

    def load(self, key):
        return cache.get(key)

    def store(self, key, value):
        print {key[15:]: value}
        cache.set(key[15:], value)

    @abstractmethod
    def process(self):
        pass
