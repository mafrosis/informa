import datetime

from flask import Blueprint, jsonify, json, request
from flask import current_app as app
from marshmallow import fields, Schema

import redis

from .base import InformaBasePlugin


bp = Blueprint('dht22', __name__, url_prefix='/api/dht22')


class Dht22Plugin(InformaBasePlugin):
    def process(self):
        pass


class TemperatureSchema(Schema):
    """
    DHT22 post data
    """
    ts = fields.Integer(required=True)
    temperature = fields.Decimal(required=True, places=2)
    humidity = fields.Decimal(required=True, places=2)


@bp.route('/', methods=['POST'])
def dht22():
    data = TemperatureSchema().load(request.get_json())

    try:
        redis_ = redis.StrictRedis(app.config['REDIS_HOST'], app.config['REDIS_PORT'])
        redis_.set('informa.plugins.dht22.Dht22Plugin', json.dumps(data))

        history = '{ts}{temperature}{humidity}'.format(**data)
        redis_.append('informa.plugins.dht22.Dht22Plugin.history', history)

    except redis.exceptions.ConnectionError:
        return jsonify({'message': 'Redis is down'}, 500)

    return jsonify({'message': 'OK'})
