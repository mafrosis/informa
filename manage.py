#! /usr/bin/env python

from __future__ import absolute_import
from flask.ext.script import Manager

import json

from inform import app, db, views

manager = Manager(app)


@manager.command
def get():
    """
    Inspect the data in memcache
    """
    print views.get().data


@manager.command
def load(plugin_name):
    """
    Foreground load data via a single plugin
    """
    if plugin_name in app.config['plugins'].keys():
        output = {
            plugin_name: app.config['plugins'][plugin_name].run(force=True)
        }

    print json.dumps(output, indent=2)


@manager.command
def forcepoll():
    """
    Load new data for each plugin now
    """
    views.poll()


@manager.command
def init_db():
    """
    Initialise the DB with the SQLAlchumy schema
    """
    db.create_all()


@manager.command
def check_pip():
    import xmlrpclib
    import pip

    pypi = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
    for dist in pip.get_installed_distributions():
        available = pypi.package_releases(dist.project_name)
        if not available:
            # Try to capitalize pkg name
            available = pypi.package_releases(dist.project_name.capitalize())

        if not available:
            msg = 'no releases at pypi'
        elif available[0] != dist.version:
            msg = '{} available'.format(available[0])
        else:
            msg = 'up to date'
        pkg_info = '{dist.project_name} {dist.version}'.format(dist=dist)
        print '{pkg_info:40} {msg}'.format(pkg_info=pkg_info, msg=msg)


if __name__ == "__main__":
    manager.run()
