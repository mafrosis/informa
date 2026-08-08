import copy
import datetime
import decimal
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List

import bs4
import click
import googleapiclient
import gspread
import pandas as pd
import requests
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe

from gmsa import Gmail
from informa import app
from informa.lib import PluginAdapter, StateBase, pretty
from informa.lib.plugin import InformaPlugin
from informa.lib.utils import raise_alarm

logger = PluginAdapter(logging.getLogger('informa'))


SPREADO_ID = '1hK-10ucfebKcQng0gOC5VOELEvEGUIRbJUKxZQ1m5bA'


class NoExtractionError(Exception):
    pass


@dataclass
class Wine:
    tag: str  # Daft TOB tag
    price: decimal.Decimal
    url: str | None = None  # Product page URL
    image_url: str | None = None
    paid: decimal.Decimal | None = None  # Paid price
    title: str | None = None  # Actual wine name
    index: int | None = None  # Index in the order
    identifier: str | None = None  # Composed from order+wine info


@dataclass
class Order:
    number: int
    date: datetime.date
    total: decimal.Decimal
    discount: decimal.Decimal
    wines: List[Wine] = field(default_factory=list)


@dataclass
class OrderLine:
    price: decimal.Decimal
    quantity: int


@dataclass
class State(StateBase):
    orders: List[Order] = field(default_factory=list)


@app.task('every 12 hours')
def run(plugin):
    plugin.execute()


def main(state: State) -> int:
    gsuite_creds = os.environ.get('GSUITE_OAUTH_CREDS')
    if not gsuite_creds:
        logger.error('No Google service account credentials')
        return 0

    gc = gspread.service_account(filename=gsuite_creds)

    sheet = gc.open_by_key(SPREADO_ID).worksheet('raw')

    # The spreadsheet is the source of truth for persisted order history.
    df = get_as_dataframe(sheet)
    merge_upstream(df, state.orders)

    msgs = check_for_email()
    if msgs is None:
        return

    order = None

    try:
        # Parse the first order
        if (msg := next(iter(msgs), None)) and (order := parse_email(msg.html)) and order:
            logger.info('Order %s found, with %s wines', order.number, len(order.wines))
            msg.mark_as_read()
    except NoExtractionError:
        raise_alarm(logger, f'Email dated {msg.date} failed extraction')
        return 0

    # Add a newly parsed order to the upstream history.
    if order and order.number not in (o.number for o in state.orders):
        state.orders.append(order)

    if state.orders:
        # Write to Google Sheets
        set_with_dataframe(sheet, get_history(state), resize=True)

    if order:
        return len(order.wines)
    return 0


def check_for_email(query: str | None = None) -> Order | None:
    'Fetch theotherbordeaux emails from the wines label'
    try:
        gmail = Gmail(
            credentials=Credentials.from_service_account_file(
                os.environ.get('GSUITE_OAUTH_CREDS'),
                scopes=['https://www.googleapis.com/auth/gmail.modify'],
                subject='m@mafro.net',
            )
        )
    except TypeError:
        logger.error('Bad SSH private key defined in GSUITE_OAUTH_CREDS')
        return None
    except googleapiclient.errors.HttpError:
        logger.error('Failed to authenticate to the Google API')
        return None

    try:
        bquery = 'label:wines from:tom@theotherbordeaux.com '

        # Fetch the supplied gmail query, else anything unread
        if not query:
            query = bquery + 'is:unread'
        else:
            query = bquery + query

        msgs = gmail.get_messages(query=query)
    except googleapiclient.errors.HttpError:
        logger.error('Failed to fetch messages from Gmail')
        return None

    logger.debug(msgs)
    return msgs


def parse_email(html: str) -> Order:
    'Parse the email for the order details'
    soup = bs4.BeautifulSoup(html, 'html.parser')

    order = None

    try:
        body = soup.select_one('#body_content_inner')

        # Parse total, and attempt to parse discount
        discount = 0
        total = None
        for tr in body.select('tfoot tr, tr.order-totals'):
            th = tr.select_one('th')
            if th is None:
                continue
            text = th.text

            if text.strip().startswith('Discount'):
                discount = decimal.Decimal(tr.select_one('td').text.strip().replace('$', '')) * -1

            if text.strip().startswith('Total'):
                total = decimal.Decimal(tr.select_one('td').text.strip().replace('$', ''))

        if total is None:
            raise NoExtractionError('No total found in email')

        # Parse order table header
        header = body.select_one('h2').text.strip()

        order = Order(
            number=int(header[8 : header.index(']')]),
            date=datetime.datetime.strptime(header[header.index('(') + 1 : -1], '%B %d, %Y').date(),  # noqa: DTZ007
            total=total,
            discount=discount,
        )

    except (IndexError, TypeError) as e:
        logger.error('Failed to parse order items from email: %s (%s)', order.number if order else '?', e)
        return None

    singles = []

    try:
        # Iterate order line items
        for row in body.select('.order_item'):
            url = row.select_one('a').attrs['href']
            quantity = int(row.select('td')[1].text.strip())
            price = row.select('td')[2].text.strip()
            price = price.removeprefix('$')
            price = decimal.Decimal(price)

            wines = extract_wines(url, order_line=OrderLine(price, quantity))

            if len(wines) == 0:
                raise IndexError

            if len(wines) == 1:
                # The order email is authoritative when the product page price has since changed.
                wines[0].paid = round(price / quantity, 2)

                # Append quantity of a single wine to order
                for _ in range(quantity):
                    w = copy.deepcopy(wines[0])
                    order.wines.append(w)
                    singles.append(w)
            else:
                # Append multiple wines to order
                for _ in range(int(quantity / len(wines))):
                    for wine in wines:
                        order.wines.append(copy.deepcopy(wine))

        # Factor the discount % into the paid price for all wine
        if order.discount:
            coef = 1 - (order.discount / (order.total + order.discount))
            for wine in order.wines:
                wine.paid = round(coef * wine.paid, 2)

        if divmod(sum(w.paid for w in order.wines), 1)[0] != divmod(order.total, 1)[0]:
            raise_alarm(logger, f'Divmod fail on order: {order.number}')

        create_indentifiers(order)

    except (IndexError, TypeError, requests.RequestException) as e:
        logger.error('Failed to parse order items from email: %s (%s)', order.number, e)
        return None

    return order


def extract_wines(item_url: str, order_line: OrderLine | None = None) -> List[Wine]:
    '''
    Extract the wines listed on a TOB product page

    Params:
        item_url:  Product page URL
    Returns:
        List of Wine objects
        Pack price
    '''
    resp = requests.get(
        item_url,
        timeout=5,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
        },
    )
    soup = bs4.BeautifulSoup(resp.text, 'html.parser')
    body = soup.select_one('#tab-description')
    logger.debug('Extracting: %s', item_url)

    if body is None:
        raise NoExtractionError(f'No #tab-description found on {item_url}')

    # Clean up email text into an array
    email_text = [line.replace('\xa0', ' ').strip() for line in body.text.splitlines()]

    wines = []

    def extract_single():
        # The wine title follows the 'Description' heading in the legacy format;
        # newer ChatGPT-generated pages have it as the first h1 in the description
        description_index = next((i for i, line in enumerate(email_text) if line == 'Description'), None)
        if description_index is not None:
            title = next((line for line in email_text[description_index + 1 :] if line), '')
        else:
            desc_title = next(
                (heading for heading in body.select('h1, h2') if heading.get_text(strip=True) != 'Description'),
                None,
            )
            title = (
                desc_title.get_text(' ', strip=True) if desc_title else next((line for line in email_text if line), '')
            )

        price_text = soup.select_one('.summary .price') or soup.select_one('.price')
        prices = re.findall(r'\$\s*([\d,]+(?:\.\d+)?)', price_text.get_text(' ', strip=True)) if price_text else []
        if not prices:
            raise NoExtractionError(f'No numeric product price found on {item_url}')
        price = decimal.Decimal(prices[-1].replace(',', ''))
        tag = soup.select_one('h1').text
        image = soup.select_one('div.single-product-main-image img') or soup.select_one(
            'div.woocommerce-product-gallery img'
        )
        wine = Wine(
            title=title,
            tag=tag,
            url=item_url,
            price=price,
            image_url=image.attrs['src'] if image else None,
        )

        for i, line in enumerate(email_text):
            # If this a pre-departure, overwrite price with value from body text
            if re.search('pre-departure(.*)price', line):
                paid = line[line.index('$') + 1 :]
                paid = paid.removesuffix('.')

                wine.paid = decimal.Decimal(paid)

                if description_index is not None:
                    # In the legacy format, switch the tag and title fields
                    title = wine.tag
                    wine.tag = wine.title
                    wine.title = title
                continue

            if 'Post arrival price' in line:
                price = next(iter(re.findall(r'([\d.]*\d+)', line)), None)
                if price:
                    wine.price = decimal.Decimal(price)
                continue

        return wine

    def extract_text_pack():
        image_index = 0

        for i, line in enumerate(email_text):
            if line.startswith('#'):
                paid = price = None

                tag = line[4:].strip()
                tag = tag.removesuffix('.')

                for offset in range(4):
                    try:
                        if re.search('pre-departure(.*)price', email_text[i + offset]):
                            paid = email_text[i + offset][email_text[i + offset].index('$') + 1 :]
                            paid = paid.removesuffix('.')
                            continue

                        if 'Post arrival price' in email_text[i + offset]:
                            price = email_text[i + offset][28:]
                            continue

                    except (IndexError, ValueError):
                        continue

                image_url = body.select('img')[image_index].attrs['src']
                image_index += 1

                wines.append(
                    Wine(
                        tag=tag,
                        url=item_url,
                        price=decimal.Decimal(price),
                        paid=decimal.Decimal(paid),
                        image_url=image_url,
                    )
                )

        return wines

    if len(set(body.select('a'))) <= 1 and not bool(body.select('img')):
        # If body has no images & and one unique link, then it's a single
        return [extract_single()]

    if bool(body.select('a')):
        # Multiple links indicates a mixed pack product
        for atag in body.select('a'):
            # Ignore pack_price when querying wines in packs
            wines.extend(extract_wines(atag.attrs['href']))

        # Calculate how many multiples of packs were ordered
        # num bottles in order line divided by pack size
        num_packs = int(order_line.quantity / len(wines))
        pack_price = order_line.price / num_packs
        undiscounted_pack_price = sum(w.price for w in wines)

        for wine in wines:
            wine.paid = round(wine.price / undiscounted_pack_price * pack_price, 2)
        return wines

    if len(body.select('a')) == 0 and len(body.select('img')) > 1:
        # Handle text-only emails older than Sept '24
        return extract_text_pack()

    raise NoExtractionError


def create_indentifiers(order: Order):
    wine_seen = []

    # Create indexes & identifiers
    for wn in order.wines:
        wn.index = wine_seen.count(wn.tag) + 1
        wine_seen.append(wn.tag)
        wn.identifier = hashlib.sha256(f'{order.number}{wn.tag}{wn.index}'.encode()).hexdigest()


def merge_upstream(df: pd.DataFrame, orders: List[Order]) -> None:
    'Replace local order history with the Google Sheet order history'

    orders.clear()
    if df.empty:
        return

    rows = df[df['number'].notna()]
    for number, order_rows in rows.groupby('number', sort=False):
        first = order_rows.iloc[0]
        order = Order(
            number=int(number),
            date=pd.to_datetime(first['date']).date(),
            total=decimal.Decimal(str(first['total'])),
            discount=decimal.Decimal(str(first['discount'])),
        )

        for _, row in order_rows.iterrows():
            paid = None if pd.isna(row['wine.paid']) else decimal.Decimal(str(row['wine.paid']))
            identifier = None if pd.isna(row['wine.identifier']) else str(row['wine.identifier'])
            order.wines.append(
                Wine(
                    title=None if pd.isna(row['wine.title']) else str(row['wine.title']),
                    url=None if pd.isna(row['wine.url']) else str(row['wine.url']),
                    tag=None if pd.isna(row['wine.tag']) else str(row['wine.tag']),
                    price=decimal.Decimal(str(row['wine.price'])),
                    paid=paid,
                    image_url=None if pd.isna(row['wine.image_url']) else str(row['wine.image_url']),
                    identifier=identifier,
                )
            )

        provided_identifiers = [wine.identifier for wine in order.wines]
        if any(identifier is None for identifier in provided_identifiers):
            create_indentifiers(order)
            for wine, identifier in zip(order.wines, provided_identifiers):
                if identifier is not None:
                    wine.identifier = identifier

        orders.append(order)


@click.group(name='tob')
def cli():
    'The Other Bordeaux CLI'


def _flatten(order: Order):
    return [
        {
            'number': order.number,
            'date': order.date,
            'total': order.total,
            'discount': order.discount,
            'wine.title': w.title,
            'wine.url': w.url,
            'wine.tag': w.tag,
            'wine.price': w.price,
            'wine.paid': w.paid,
            'wine.image_url': w.image_url,
            'wine.identifier': w.identifier,
        }
        for w in order.wines
    ]


def get_history(state: State) -> pd.DataFrame:
    data = []
    for o in state.orders:
        data.extend(_flatten(o))
    df = pd.DataFrame(data)
    return df.sort_values(['number', 'wine.tag'], ascending=False)


@cli.command
def history(plugin: InformaPlugin):
    '''
    Show product stats
    '''
    df = get_history(plugin.load_state())
    df['date'] = pd.to_datetime(df['date'])
    pretty.dataframe(df)


@cli.command
@click.argument('order')
def parse(order: int):
    '''
    Parse a single order and display the wines

    \b
    ORDER   A single TOB order number
    '''
    msgs = check_for_email(str(order))
    if msg := next(iter(msgs), None):
        order = parse_email(msg.html)
        if order is None:
            return
        df = pd.DataFrame(_flatten(order))
        df['date'] = pd.to_datetime(df['date'])
        pretty.dataframe(df)
