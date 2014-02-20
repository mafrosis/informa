import json

from flask import make_response

from inform import app


def noop():
    pass


@app.route("/")
def index():
    return get()


@app.route("/get")
def get():
    data = {}

    # load each module's data from memcache
    for m in app.config['modules'].keys():
        data[m] = app.config['modules'][m].load()

    # response with formatted json
    return _make_json_response(data)


@app.route("/force-poll")
def poll():
    # force start of all plugins
    for m in app.config['modules'].keys():
        app.config['modules'][m].delay()

    return _make_json_response({'OK': True})


def _make_json_response(content, html=False):
    if app.debug:
        response = make_response(json.dumps(content, indent=2))
    else:
        response = make_response(content)

    if html == False:
        response.headers['Content-Type'] = 'application/json'

    return response
