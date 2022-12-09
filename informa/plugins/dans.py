from dataclasses import dataclass, field
import datetime
import logging
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin
import requests

from informa.lib import app, fetch_run_publish, mailgun, PluginAdapter


logger = PluginAdapter(logging.getLogger('informa'))


MQTT_TOPIC = f'informa/{__name__}'
TEMPLATE_NAME = 'dans.tmpl'


@dataclass
class Product(JsonSchemaMixin):
    id: int
    name: str
    target: int

@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)


PRODUCTS = [
    Product(110093, 'Woodford', 60),
    Product(904612, 'Tariquet', 60),
]


@app.task('every 12 hours', name=__name__)
def run():
    fetch_run_publish(logger, State, MQTT_TOPIC, main)


def main(state: State):
    logger.debug('Running, last run: %s', state.last_run or 'Never')
    state.last_run = datetime.datetime.now()

    sess = requests.Session()

    for product in PRODUCTS:
        query_product(sess, product)


def query_product(sess, product: Product) -> bool:
    logger.debug('Querying %s', product.name)
    try:
        resp = sess.get(f'https://api.danmurphys.com.au/apis/ui/Product/{product.id}', timeout=5)
    except requests.RequestException as e:
        logger.error('Failed loading from %s: %s', product.name, e)
        return False

    try:
        current_price = resp.json()['Products'][0]['Prices']['singleprice']['Value']
    except (KeyError, IndexError) as e:
        logger.error('%s parsing price', e)
        return False

    if current_price <= product.target:
        logger.info('Sending email for %s at price %s', product.name, current_price)

        mailgun.send(
            logger,
            f'Good price on {product.name}!',
            TEMPLATE_NAME,
            {
                'product': product.name,
                'price': current_price,
                'url': f'https://www.danmurphys.com.au/product/DM_{product.id}',
            }
        )
        return True

    return False
