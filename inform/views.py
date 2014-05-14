import json

from flask import make_response

from inform import app


@app.route("/")
def index():
    return get()


@app.route("/get")
def get():
    data = {}

    # load each module's data from memcache
    for name, item in app.config['plugins'].items():
        if item['enabled'] is True:
            data[name] = item['plugin'].load()

    # response with formatted json
    return _make_json_response(data)


@app.route("/force-poll")
def poll():
    data = {}

    # force start of all plugins
    for name, item in app.config['plugins'].items():
        if item['enabled'] is True:
            data[name] = item['plugin'].delay()

    return _make_json_response({'OK': True})


def _make_json_response(content, html=False):
    if app.debug:
        response = make_response(json.dumps(content, indent=2))
    else:
        response = make_response(json.dumps(content))

    if html == False:
        response.headers['Content-Type'] = 'application/json'

    return response
