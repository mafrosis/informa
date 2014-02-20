from __future__ import absolute_import

from celery import Celery

celery = Celery(broker="amqp://guest@localhost:5672/")

celery.conf.update(
    CELERY_DEFAULT_QUEUE = "inform",
    CELERY_DEFAULT_EXCHANGE = "inform",
    CELERY_DEFAULT_EXCHANGE_TYPE = "direct",
    CELERY_DEFAULT_ROUTING_KEY = "inform",

    CELERY_RESULT_BACKEND = "cache",
    CELERY_CACHE_BACKEND = "memcached://127.0.0.1:11211/",
    CELERY_TASK_RESULT_EXPIRES = None,
)
