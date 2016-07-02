#! /usr/bin/env python
import json

from flask_script import Manager

from informa.app import create_app

app = create_app()
manager = Manager(app)

# convenient entrypoint for celery worker
celery = app.celery


@manager.command
def load(name):
    """
    Foreground load data via a single plugin
    """
    plugin = app.config['plugins'].get('plugins.{}'.format(name))

    if not plugin:
        print('Unknown plugin')
        return

    if plugin['enabled']:
        print(
            json.dumps({name: plugin['cls'].run(force=True)}, indent=2)
        )
    else:
        print('Plugin disabled')


@manager.command
def forcepoll():
    """
    Load new data for each plugin now
    """
    import views
    views.poll()


@manager.command
def check_pip():
    import xmlrpc
    import pip

    pypi = xmlrpc.client.ServerProxy('https://pypi.python.org/pypi')
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
        print('{pkg_info:40} {msg}'.format(pkg_info=pkg_info, msg=msg))


if __name__ == "__main__":
    manager.run()
