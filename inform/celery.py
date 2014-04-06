from __future__ import absolute_import

from celery import Celery

celery = Celery(broker='sqla+sqlite:////srv/inform/inform.sqlitedb')
