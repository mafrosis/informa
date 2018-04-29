from flask import Blueprint, current_app as app, jsonify, request

bp = Blueprint('base', __name__)


@bp.route('/')
def index():
    return get()


@bp.route('/get')
@bp.route('/get/<plugin>')
def get(plugin=None):
    data = {}

    force = bool(request.args.get('force', 0))

    if not plugin:
        # load each module's latest data
        for plugin_name in app.config['plugins']['enabled']:
            data[plugin_name] = app.config['cls'][plugin_name].get(force=force)

    else:
        # if requested plugin is not already enabled, load it
        if plugin not in app.config['plugins']['enabled']:
            from informa.app import load_plugin
            load_plugin(app, 'informa.plugins.{}'.format(plugin))

        # load plugin data
        data = app.config['cls'][plugin].get(force=force)

    return jsonify(data)


@bp.route('/force-poll')
def poll():
    # force background load of all plugins
    for name, plugin in app.config['plugins'].items():
        if plugin['enabled'] is True:
            plugin['cls'].delay()

    return jsonify({'OK': True})
