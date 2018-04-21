from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import decimal

from flask import json


class CustomJSONEncoder(json.JSONEncoder):
    '''
    Override Flask's JSONEncoder with the single method `default`, which is called when
    the encoder doesn't know how to encode a specific type.

    Objects of type `decimal.Decimal` are serialised with `str()` and `datetime.datetime`
    is returned as isoformat.

    Any other objects are checked for presence of a `__json__` method which must return
    JSON serialisable data.
    '''
    def default(self, obj):
        if type(obj) is decimal.Decimal:
            return str(obj)

        if type(obj) in (datetime.date, datetime.datetime):
            return obj.isoformat()

        if hasattr(obj.__class__, '__json__') and callable(obj.__json__):
            return obj.__json__()

        else:
            # raises TypeError: obj not JSON serializable
            return json.JSONEncoder.default(self, obj)


def init_json(app):
    '''
    Use custom JSON encoder with Flask
    '''
    app.json_encoder = CustomJSONEncoder
