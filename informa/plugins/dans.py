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
class History(JsonSchemaMixin):
    product: Product
    price: decimal.Decimal
    ts: datetime.datetime = field(default=now_aest())
    alerted: bool = field(default=False)

@dataclass
class State(JsonSchemaMixin):
    last_run: Optional[datetime.date] = field(default=None)
    history: List[History] = field(default_factory=list)

class FailedProductQuery(Exception):
    pass

class ProductNeverAlerted(Exception):
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

    history_item: Optional[History] = None

    # Iterate configured list of Dan's products
    for product in config.products:
        try:
            history_item, _ = get_last_alert(product, state.history)
        except ProductNeverAlerted:
            pass

        try:
            current_price = query_product(sess, product)
            alerted = False

            # Check if price within target range, and send an email if so
            if current_price <= product.target:
                # Skip product if alerted more recently than 6 days ago
                if history_item and history_item.ts > now_aest() - datetime.timedelta(days=6):
                    logger.info('Skipped alerting %s @ %s', product.name, history_item.price)
                else:
                    send_alert(product, current_price)
                    alerted = True

            # Track query results
            result = History(product, current_price, alerted=alerted)
            add_to_history(state.history, result)

        except FailedProductQuery as e:
            logger.error(e)


def get_last_alert(product: Product, history: List[History]) -> Tuple[History, int]:
    'Lookup most recent alert for this product'
    for i, history_item in enumerate(reversed(history)):
        if history_item.product == product and history_item.alerted:
            return history_item, i
    raise ProductNeverAlerted


def add_to_history(history: List[History], new_history: History):
    'Add query result to product history'
    # Remove history over 13 months old
    for i, history_item in enumerate(history):
        if history_item.ts > now_aest() + datetime.timedelta(days=400):
            del history[i]

    history.append(new_history)


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
