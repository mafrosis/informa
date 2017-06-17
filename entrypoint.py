import json

import click

from informa.app import create_app

app = create_app()

# convenient entrypoint for celery worker
celery = app.celery


@app.cli.command()
@click.argument('name', required=True)
def load(name):
    '''
    Foreground load data via a single plugin
    '''
    if name not in app.config['cls']:
        print('Unknown plugin')
        return

    data = app.config['cls'][name].run(force=True)
    print(json.dumps({name: data}, indent=2))


@app.cli.command()
def forcepoll():
    """
    Load new data for each plugin now
    """
    import views
    views.poll()


@app.cli.command()
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
