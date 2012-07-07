from flask import Flask
from flask.ext.celery import Celery

BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_VHOST = "/"
BROKER_USER = "guest"
BROKER_PASSWORD = "guest"

CELERY_RESULT_BACKEND = "amqp"
CELERY_IGNORE_RESULT = True

app = Flask(__name__)
app.config.from_pyfile("../config/flask.conf.py")

modules = {}

celery = Celery(app)

import os
import views

# find and import all plugins
for root, dirs, files in os.walk('inform/plugins'):
    for filename in files:
        if not filename.startswith("__") and filename.endswith('.py'):
            modname = filename[:-3]
            try:
                mod = __import__("plugins.%s" % modname, globals(), locals(), ['InformPlugin'], -1)
                modules[modname] = mod.InformPlugin()
            except (ImportError, AttributeError):
                print "Bad plugin: %s" % modname
                pass


if __name__ == '__main__':
    app.run()
