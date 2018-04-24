from flask import Blueprint, jsonify
from flask import current_app as app

bp = Blueprint('base', __name__)


@bp.route('/')
def index():
    return get()


@bp.route('/get')
@bp.route('/get/<plugin>')
def get(plugin=None):
    data = {}

    if not plugin:
        # load each module's latest data
        for plugin_name in app.config['plugins']['enabled']:
            data[plugin_name] = app.config['cls'][plugin_name].load()

    else:
        data = app.config['cls'][plugin].load()

    return jsonify(data)


@bp.route('/force-poll')
def poll():
    # force background load of all plugins
    for name, plugin in app.config['plugins'].items():
        if plugin['enabled'] is True:
            plugin['cls'].delay()

    return jsonify({'OK': True})
