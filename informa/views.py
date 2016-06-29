from flask import jsonify

from informa import app


@app.route('/')
def index():
    return get()


@app.route('/get')
@app.route('/get/<plugin>')
def get(plugin=None):
    data = {}

    if not plugin:
        # load each module's latest data
        for name, plugin in app.config['plugins'].items():
            if plugin['enabled'] is False:
                continue

            data[name.replace('plugins.','')] = plugin['cls'].load()
    else:
        plugin = app.config['plugins'].get('plugins.{}'.format(plugin))
        data = plugin['cls'].load()

    return jsonify(data=data)


@app.route('/force-poll')
def poll():
    # force background load of all plugins
    for name, plugin in app.config['plugins'].items():
        if plugin['enabled'] is True:
            plugin['cls'].delay()

    return jsonify({'OK': True})