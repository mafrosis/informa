from dataclasses import dataclass, field
import datetime
import decimal
import logging
from typing import List, Optional, Tuple

from dataclasses_jsonschema import JsonSchemaMixin
import requests

from informa.lib import app, ConfigBase, load_run_persist, mailgun, now_aest, PluginAdapter


logger = PluginAdapter(logging.getLogger('informa'))


PLUGIN_NAME = __name__
TEMPLATE_NAME = 'dans.tmpl'


@dataclass
class Product(JsonSchemaMixin):
    id: str
    name: str
    target: int

@dataclass
class Alert(JsonSchemaMixin):
    product: Product
    price: decimal.Decimal
    ts: datetime.datetime = field(default=now_aest())

@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)
    alerted: List[Alert] = field(default_factory=list)

class FailedProductQuery(Exception):
    pass


@dataclass
class Config(ConfigBase):
    products: List[Product]


@app.task('every 12 hours', name=__name__)
def run():
    load_run_persist(logger, State, PLUGIN_NAME, main)


def main(state: State, config: Config):
    logger.debug('Running, last run: %s', state.last_run or 'Never')
    state.last_run = now_aest()

    sess = requests.Session()

    # Iterate configured list of Dan's products
    for product in config.products:
        alert, _ = get_last_alert(product, state.alerted)

        # Skip product if alerted more recently than 6 days ago
        if alert and alert.ts > now_aest() - datetime.timedelta(days=6):
            logger.info('Skipped recently alerted %s @ %s', product.name, alert.price)
            continue

        try:
            current_price = query_product(sess, product)

            # Check if price within target range, and send an email if so
            if current_price <= product.target:
                send_alert(product, current_price)
                update_product_alert(product, current_price, state.alerted)

        except FailedProductQuery as e:
            logger.error(e)


def get_last_alert(product: Product, alerts: List[Alert]) -> Tuple[Optional[Alert], Optional[int]]:
    'Lookup most recent alert for this product'
    for i, alert in enumerate(alerts):
        if alert.product == product:
            return alert, i
    return None, None


def update_product_alert(product: Product, current_price: decimal.Decimal, alerts: List[Alert]):
    'Update the alert for this product'
    # Remove previous alert for this product
    _, i = get_last_alert(product, alerts)
    if i:
        del alerts[i]

    # Create new alert timestamp for this product
    alerts.append(Alert(product, current_price, now_aest()))


def query_product(sess, product: Product) -> decimal.Decimal:
    '''
    Query Dan Murphy's API for a product's current pricing

    Params:
        sess:     Requests session
        product:  Product to query for
    Returns:
        Return the current price
    '''
    try:
        # Fetch single product from Dan's API
        resp = sess.get(f'https://api.danmurphys.com.au/apis/ui/Product/{product.id}', timeout=5)
    except requests.RequestException as e:
        raise FailedProductQuery(f'Failed loading from {product.name}: {e}')

    try:
        # Pull out the current single bottle price
        prices = resp.json()['Products'][0]['Prices']
        if 'promoprice' in prices:
            prices = prices['promoprice']
        else:
            prices = prices['singleprice']

        # Continue with current price as decimal
        current_price = decimal.Decimal(str(prices['Value']))

    except (KeyError, IndexError) as e:
        raise FailedProductQuery(f'{e.__class__.__name__} {e} parsing price for {product.name}')

    logger.debug('Querying %s %s for target=%s, actual=%s', product.id, product.name, product.target, current_price)

    return current_price


def send_alert(product: Product, current_price: decimal.Decimal):
    'Send alert email via Mailgun'
    logger.info('Sending email for %s @ %s', product.name, current_price)

    mailgun.send(
        logger,
        f'Good price on {product.name}',
        TEMPLATE_NAME,
        {
            'product': product.name,
            'price': current_price,
            'url': f'https://www.danmurphys.com.au/product/DM_{product.id}',
        }
    )
