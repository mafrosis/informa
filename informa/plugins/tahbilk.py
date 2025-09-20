import logging
from dataclasses import dataclass, field

import bs4
import click
import requests

from informa import app
from informa.lib import PluginAdapter, StateBase, mailgun
from informa.lib.plugin import InformaPlugin, click_pass_plugin

logger = PluginAdapter(logging.getLogger('informa'))


TEMPLATE_NAME = 'product_price_url.tmpl'


@dataclass(frozen=True)  # Immutable, hashable
class WineRelease:
    title: str
    price: str
    url: str


@dataclass
class State(StateBase):
    products_seen: set[WineRelease] = field(default_factory=set)


@app.task('every 12 hours')
def run(plugin):
    plugin.execute()


def main(state: State) -> int:
    return query_cellar_releases(state.products_seen)


def query_cellar_releases(products_seen: set[str]) -> int:
    try:
        resp = requests.get('https://www.tahbilk.com.au/tahbilk-museum-release', timeout=5)
    except requests.RequestException as e:
        logger.error('Failed loading Tahbilk website: %s', e)
        return None

    soup = bs4.BeautifulSoup(resp.text, 'html.parser')

    found = 0

    # Iterate all products
    for product_info in soup.select('a.product-info'):
        wr = WineRelease(
            title=product_info.select_one('h4').text,
            url='https://www.tahbilk.com.au' + product_info.attrs['href'],
            price=product_info.select_one('.wine-club-price .price').text,
        )

        # Alert on anything not already seen
        if wr not in products_seen:
            products_seen.add(wr)
            logger.info('Found %s at %s', wr.title, wr.price)
            found += 1
            notify(wr)

    return found


def notify(wr: WineRelease):
    mailgun.send(
        logger,
        f'New Tahbilk release: {wr.title}',
        TEMPLATE_NAME,
        {
            'title': wr.title,
            'price': wr.price,
            'url': wr.url,
        },
    )


@click.group(name=__name__[16:])
def cli():
    'Tahbilk new release tracker'


@cli.command
@click_pass_plugin
def seen(plugin: InformaPlugin):
    'What products have been seen already?'
    state = plugin.load_state()
    print('\n'.join([f'{wr.title} @ {wr.price}' for wr in state.products_seen]))
