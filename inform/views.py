from inform import app, modules
from flask import make_response

import json

@app.route("/")
def index():
    return get()


@app.route("/get")
def get():
    data = {}

    # load each module's data from memcache
    for m in modules.keys():
        data[m] = modules[m].load(m)

    # response with formatted json
    return _make_json_response(data)


@app.route("/force-poll")
def poll():
    # force start of all plugins
    for m in modules.keys():
        modules[m].delay()

    return _make_json_response({'OK': True})


def _make_json_response(content):
    if app.debug:
        response = make_response(json.dumps(content, indent=4))
    else:
        response = make_response(content)

    response.headers['Content-Type'] = 'application/json'
    return response
