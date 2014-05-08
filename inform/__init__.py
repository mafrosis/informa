from __future__ import absolute_import

# setup Flask
from flask import Flask
app = Flask(__name__)
app.config.from_pyfile("../config/flask.conf.py")

from .celery import celery

# find and import all plugins
app.config['modules'] = {}

import os
from . import views
views.noop()

for root, dirs, files in os.walk('inform/plugins'):
    for filename in files:
        if not filename.startswith('__') and filename.endswith('.py'):
            modname = filename[:-3]

            try:
                mod = __import__('plugins.{}'.format(modname), globals(), locals(), ['InformPlugin'], -1)

                if getattr(mod.InformPlugin, 'enabled', True):
                    m = mod.InformPlugin()
                    m.plugin_name = modname
                    app.config['modules'][modname] = m
                    print 'Active plugin: {}'.format(modname)
                else:
                    print 'Inactive plugin: {}'.format(modname)

            except (ImportError, AttributeError) as e:
                # TODO add debug param
                print 'Bad plugin: {} ({})'.format(modname, e)
                pass


if __name__ == '__main__':
    app.run()
