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
from informa.lib import PluginAdapter, StateBase, app, pretty
from informa.lib.plugin import load_state, load_run_persist

logger = PluginAdapter(logging.getLogger('informa'))


SPREADO_ID = '1hK-10ucfebKcQng0gOC5VOELEvEGUIRbJUKxZQ1m5bA'


class NotImplementedError(Exception):
    pass


@dataclass
class Wine:
    tag: str    # Daft TOB tag
    url: str    # Product page URL
    price: decimal.Decimal
    image_url: str
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
class State(StateBase):
    orders: List[Order] = field(default_factory=list)


@app.task('every 12 hours', name=__name__)
def run():
    load_run_persist(logger, State, main)


def main(state: State) -> int:
    gc = gspread.service_account(filename=os.environ.get('GSUITE_OAUTH_CREDS'))

    sheet = gc.open_by_key(SPREADO_ID).worksheet('raw')

    # Fetch from Google Sheets, and overwrite the state.orders
    if state.orders:
        df = get_as_dataframe(sheet)
        merge_upstream(df, state.orders)

    order = check_for_email()

    # If the order is new, add it to the state
    if order and order.number not in (o.number for o in state.orders):
        state.orders.append(order)

    if state.orders:
        # Write to Google Sheets
        set_with_dataframe(sheet, get_history(state), resize=True)

    if order:
        return len(order.wines)
    return 0


def check_for_email() -> Order:
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
        # Fetch UNREAD messages from theotherbordeaux
        msgs = gmail.get_messages(query='label:wines from:tom@theotherbordeaux.com is:unread')
    except googleapiclient.errors.HttpError:
        logger.error('Failed to fetch messages from Gmail')
        return None

    logger.debug(msgs)

    try:
        if (msg := next(iter(msgs), None)) and (order := parse_email(msg.html)):
            if order:
                logger.info('Order %s found, with %s wines', order.number, len(order.wines))
                # Mark the email as read
                msg.mark_as_read()
            return order

    except NotImplementedError:
        logger.error('Email dated %s not implemented', msg.date)


def parse_email(html: str) -> Order:
    'Parse the email for the order details'
    soup = bs4.BeautifulSoup(html, 'html.parser')

    try:
        body = soup.select_one('#body_content_inner')

        # Parse total, and attempt to parse discount
        discount = 0
        for tr in body.select('tfoot tr'):
            text = tr.select_one('th').text

            if text.startswith('Discount'):
                discount = decimal.Decimal(tr.select_one('td').text.strip().replace('$', '')) * -1

            if text.startswith('Total'):
                total = decimal.Decimal(tr.select_one('td').text.strip().replace('$', ''))

        # Parse order table header
        header = body.select_one('h2').text.strip()

        order = Order(
            number=int(header[8:header.index(']')]),
            date=datetime.datetime.strptime(header[header.index('(') + 1:-1], '%B %d, %Y').date(),  # noqa: DTZ007
            total=total,
            discount=discount,
        )

    except (IndexError, TypeError):
        logger.error('Failed to parse order details from email')
        return None

    try:
        singles = []

        # Iterate order line items
        for row in body.select('.order_item'):
            # name = row.select_one('a').text.strip()
            url = row.select_one('a').attrs['href']
            quantity = int(row.select('td')[1].text.strip())

            wines = extract_wines(url)

            if len(wines) == 1:
                # Append quantity of a single wine to order
                for _ in range(quantity):
                    order.wines.append(copy.deepcopy(wines[0]))
                    singles.append(copy.deepcopy(wines[0]))
            else:
                # Append multiple wines to order
                for _ in range(int(quantity / len(wines))):
                    for wine in wines:
                        order.wines.append(copy.deepcopy(wine))

        # Factor the discount % into the paid price for single bottles
        if order.discount:
            # Calculate the discount coefficient
            coef = 1 - (order.discount) / (order.total + order.discount)
            for wine in singles:
                wine.paid = coef * wine.price

        create_indentifiers(order)

    except (IndexError, TypeError, requests.RequestException):
        logger.error('Failed to parse order items from email')
        return None

    return order


def extract_wines(item_url: str) -> List[Wine]:
    '''
    Identify the wine(s) included in a single line item of an order
    '''
    resp = requests.get(item_url, timeout=5)
    soup = bs4.BeautifulSoup(resp.text, 'html.parser')
    body = soup.select_one('#tab-description')

    # Clean up email text into an array
    email_text = [line.replace('\xa0', ' ').strip() for line in body.text.splitlines()]

    wines = []

    def extract_single():
        for i, line in enumerate(email_text):
            if line == 'Description':
                title = email_text[i + 1].strip()
                price = soup.select_one('.price').text
                if price.startswith('$'):
                    price = price[1:]
                tag = soup.select_one('h1').text
                image_url = soup.select_one('div.single-product-main-image img').attrs['src']
                return Wine(title=title, tag=tag, url=item_url, price=decimal.Decimal(price), image_url=image_url)

    def extract_text_pack():
        image_index = 0

        for i, line in enumerate(email_text):
            if line.startswith('#'):
                paid = price = None

                tag = line[4:].strip()
                if tag.endswith('.'):
                    tag = tag[:-1]

                for offset in range(3):
                    try:
                        if re.search('pre-departure(.*)price', email_text[i + offset]):
                            paid = email_text[i + offset][email_text[i + offset].index('$') + 1:]
                            if paid.endswith('.'):
                                paid = paid[:-1]
                                continue

                        if 'Post arrival price' in email_text[i + offset]:
                            price = email_text[i + offset][28:]
                            continue

                    except (IndexError, ValueError):
                        continue

                image_url = body.select('img')[image_index].attrs['src']
                image_index += 1

                wines.append(Wine(
                    tag=tag,
                    url=item_url,
                    price=decimal.Decimal(price),
                    paid=decimal.Decimal(paid),
                    image_url=image_url
                ))

        return wines


    if 'mixed 6-pack' in body.text.lower():
        for wine in body.select('a'):
            wines.extend(extract_wines(wine.attrs['href']))
        return wines

    elif 'mixed dozen' in body.text.lower():
        # TODO not implemented
        raise NotImplementedError

    elif 'essentials 6-Pack' in body.text.lower():
        return extract_text_pack()

    elif 'pre-departure' in body.text.lower():
        return extract_text_pack()
    else:
        return [extract_single()]


def create_indentifiers(order: Order):
    wine_seen = []

    # Create indexes & identifiers
    for wn in order.wines:
        wn.index = wine_seen.count(wn.tag) + 1
        wine_seen.append(wn.tag)
        wn.identifier = hashlib.sha256(f'{order.number}{wn.tag}{wn.index}'.encode()).hexdigest()


def merge_upstream(df: pd.DataFrame, orders: List[Order]) -> pd.DataFrame:
    'Merge any changes made in the Google Sheet back into local state'

    # Import wine.title, wine.paid from upstream
    for _, row in df[~df['wine.identifier'].isnull()].iterrows():
        order = next((o for o in orders if o.number == row['number']), None)
        if order:
            wine = next((w for w in order.wines if w.identifier == row['wine.identifier']), None)
            if wine:
                wine.title = row['wine.title']
                wine.paid = row['wine.paid']
            else:
                raise ValueError('Invalid wine identifier in upstream data')
        else:
            raise ValueError('Invalid order number in upstream data')

    # Add new wines to respective orders
    for _, row in df[df['wine.identifier'].isnull()].iterrows():
        order = next((o for o in orders if o.number == row['number']), None)
        if order:
            order.wines.append(
                Wine(
                    title=row['wine.title'],
                    url=row['wine.url'],
                    tag=row['wine.tag'],
                    price=row['wine.price'],
                    paid=row['wine.paid'],
                    image_url=row['wine.image_url'],
                )
            )
            create_indentifiers(order)
        else:
            raise ValueError('Invalid order number in upstream data')


@click.group(name=__name__[16:])
def cli():
    'The Other Bordeaux CLI'


def get_history(state: State | None=None) -> pd.DataFrame:
    if state is None:
        state = load_state(logger, State)

    df = pd.DataFrame([
        {
            'number': o.number,
            'date': o.date,
            'total': o.total,
            'discount': o.discount,
            'wine.title': w.title,
            'wine.url': w.url,
            'wine.tag': w.tag,
            'wine.price': w.price,
            'wine.paid': w.paid,
            'wine.image_url': w.image_url,
            'wine.identifier': w.identifier,
        }
        for o in state.orders
        for w in o.wines
    ])
    df = df.sort_values(['number', 'wine.tag'], ascending=False)
    return df


@cli.command
def stats():
    '''
    Show product stats
    '''
    df = get_history()
    pretty.dataframe(df)
