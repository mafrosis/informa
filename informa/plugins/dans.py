from dataclasses import dataclass, field
import datetime
import logging
from typing import cast, List, Optional, Tuple

from dataclasses_jsonschema import JsonSchemaMixin
import requests

from informa.lib import app, fetch_run_publish, load_config, mailgun, now_aest, PluginAdapter


logger = PluginAdapter(logging.getLogger('informa'))


MQTT_TOPIC = f'informa/{__name__}'
TEMPLATE_NAME = 'dans.tmpl'


@dataclass
class Product(JsonSchemaMixin):
    id: int
    name: str
    target: int

@dataclass
class Alert(JsonSchemaMixin):
    product: Product
    ts: datetime.datetime = field(default=now_aest())

@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)
    alerted: List[Alert] = field(default_factory=list)

@dataclass
class Config(JsonSchemaMixin):
    products: List[Product]


@app.task('every 12 hours', name=__name__)
def run():
    fetch_run_publish(logger, State, MQTT_TOPIC, main)


def main(state: State):
    logger.debug('Running, last run: %s', state.last_run or 'Never')
    state.last_run = now_aest()

    # Reload config each time plugin runs
    config = cast(Config, load_config(Config, __name__))

    sess = requests.Session()

    for product in config.products:
        alert, _ = get_last_alert(product, state.alerted)

        # Skip product if alerted more recently than 6 days ago
        if alert and alert.ts > now_aest() - datetime.timedelta(days=6):
            logger.info('Skipped recently alerted %s', product.name)
            continue

        if query_product(sess, product):
            update_product_alert(product, state.alerted)


def get_last_alert(product: Product, alerts: List[Alert]) -> Tuple[Optional[Alert], Optional[int]]:
    'Lookup most recent alert for this product'
    for i, alert in enumerate(alerts):
        if alert.product == product:
            return alert, i
    return None, None


def update_product_alert(product: Product, alerts: List[Alert]):
    'Update the alert for this product'
    # Remove previous alert for this product
    _, i = get_last_alert(product, alerts)
    if i:
        del alerts[i]

    # Create new alert timestamp for this product
    alerts.append(Alert(product, now_aest()))


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
