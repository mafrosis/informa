# setup Celery
from inform.celery import celery

# setup Flask
from flask import Flask
app = Flask(__name__)
app.config.from_pyfile("../config/flask.conf.py")


# find and import all plugins
modules = {}

import os
import views

for root, dirs, files in os.walk('inform/plugins'):
    for filename in files:
        if not filename.startswith("__") and filename.endswith('.py'):
            modname = filename[:-3]

            try:
                mod = __import__("plugins.%s" % modname, globals(), locals(), ['InformPlugin'], -1)
                modules[modname] = mod.InformPlugin()
                print "Loaded plugin: %s" % modname

            except (ImportError, AttributeError):
                print "Bad plugin: %s" % modname
                pass


if __name__ == '__main__':
    app.run()
