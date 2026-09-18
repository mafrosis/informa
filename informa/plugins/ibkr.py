import csv
import datetime
import io
import logging
import os
import time
from dataclasses import dataclass, field
from typing import cast

import click
import gspread
import pandas as pd
import requests
from gspread.utils import ValueInputOption
from rocketry.conds import cron

from informa import app
from informa.exceptions import AppError
from informa.lib import ConfigBase, PluginAdapter, StateBase, pretty
from informa.lib.plugin import InformaPlugin
from informa.lib.utils import now_aest

logger = PluginAdapter(logging.getLogger('informa'))


SPREADSHEET_ID = '1iZVl2U60McLxANzjZ7_0WLJQpTwK-LCm3YYKb7luel4'
WORKSHEET_NAME = 'Current'

# Columns of the Current sheet into which the latest positions are rendered
CURRENT_COLUMNS = ('Symbol', 'Quantity', 'MarkPrice', 'CostBasisPrice')

BASE_URL = 'https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService'
HEADERS = {'User-Agent': 'Informa'}

# IBKR Flex report generation can be slow after the request is submitted
MAX_RETRIES = 5
RETRY_DELAY_S = 8


class FlexQueryError(AppError):
    'IBKR Flex Web Service request failed'


@dataclass
class Position:
    symbol: str | None
    description: str | None
    asset_class: str | None
    sub_category: str | None
    conid: str | None
    quantity: float | None
    mark_price: float | None
    position_value: float | None
    cost_basis_price: float | None
    cost_basis_money: float | None
    fifo_pnl_unrealized: float | None
    currency: str | None


@dataclass
class CashBalance:
    currency: str
    ending_cash: float | None
    ending_settled_cash: float | None


@dataclass
class Portfolio:
    fetched_at: datetime.datetime
    positions: list[Position] = field(default_factory=list)
    cash: list[CashBalance] = field(default_factory=list)


@dataclass
class Section:
    'A section of the Flex report CSV, with its headers and data rows'

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class State(StateBase):
    portfolio: Portfolio | None = None


@dataclass
class Config(ConfigBase):
    'Plugin configuration, loaded from config/ibkr.yaml'

    query_id: str


@app.task(cron('30 9 * * *'))
def run(plugin):
    plugin.execute()


def main(state: State, config: Config) -> int:
    'Fetch the portfolio via the Flex Web Service, render into state and a Google Sheet'
    token = os.environ.get('IBKR_FLEX_TOKEN')
    if not token:
        logger.error('IBKR_FLEX_TOKEN environment variable is not set')
        return 0

    ref = send_request(token, config.query_id)
    raw = get_statement(token, ref)

    # The report format is set by the query template in Client Portal, and must be TEXT (CSV)
    if raw.lstrip().startswith('<'):
        raise FlexQueryError('Flex statement returned as XML; set the query Format to TEXT (CSV) in Client Portal')

    portfolio = extract_portfolio(parse_sections(raw))
    if not portfolio.positions and not portfolio.cash:
        logger.error('Flex statement contained no positions or cash balances')
        return 0

    state.portfolio = portfolio
    logger.info('Fetched %d positions and %d cash balances', len(portfolio.positions), len(portfolio.cash))

    write_to_gsheet(portfolio)

    return len(portfolio.positions) + len(portfolio.cash)


def send_request(token: str, query_id: str) -> str:
    '''
    Submit the Flex Query and return the reference code

    Args:
        token:  Flex Web Service token
        query_id:  Flex Query ID configured in Client Portal

    Returns:
        The reference code used to retrieve the report

    Raises:
        FlexQueryError: If the request fails or the response cannot be parsed
    '''
    try:
        params: dict[str, str | int] = {'t': token, 'q': query_id, 'v': 3}
        resp = requests.get(
            f'{BASE_URL}/SendRequest',
            params=params,
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise FlexQueryError(f'SendRequest failed: {e}') from e

    # The response is a small XML fragment even when the report format is CSV
    text = resp.text
    if '<Status>Success</Status>' not in text:
        raise FlexQueryError(f'SendRequest failed: {text}')

    try:
        start = text.index('<ReferenceCode>') + len('<ReferenceCode>')
        end = text.index('</ReferenceCode>')
        ref = text[start:end].strip()
    except ValueError as e:
        raise FlexQueryError('No ReferenceCode in SendRequest response') from e

    logger.debug('Reference code: %s', ref)
    return ref


def get_statement(token: str, ref_code: str) -> str:
    '''
    Retrieve the generated report, retrying while IBKR prepares it

    Args:
        token:  Flex Web Service token
        ref_code:  Reference code returned by send_request

    Returns:
        The raw CSV report contents

    Raises:
        FlexQueryError: If the report is not available after MAX_RETRIES attempts
    '''
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            params: dict[str, str | int] = {'q': ref_code, 't': token, 'v': 3}
            resp = requests.get(
                f'{BASE_URL}/GetStatement',
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise FlexQueryError(f'GetStatement failed: {e}') from e

        # IBKR returns a small XML error while the report is still generating
        if '<status>fail</status>' in resp.text.lower() or '<ErrorMessage>' in resp.text:
            if attempt == MAX_RETRIES:
                raise FlexQueryError(f'Statement not ready after {MAX_RETRIES} attempts: {resp.text}')

            logger.info('Report not ready yet, waiting %ds (attempt %d/%d)', RETRY_DELAY_S, attempt, MAX_RETRIES)
            time.sleep(RETRY_DELAY_S)
            continue

        return resp.text

    raise FlexQueryError('Exhausted retries')


def _norm(field: str) -> str:
    'Normalise a section or header name for matching, ignoring case and spaces'
    return field.strip().lower().replace(' ', '')


# A distinctive field from each section's header row, used to identify sections
SECTION_SIGNATURES = {
    'accountinformation': 'clientaccountid',
    'cashreport': 'startingcash',
    'openpositions': 'quantity',
}


def parse_sections(raw: str) -> dict[str, Section]:
    '''
    Parse the Flex report CSV into a mapping of section name to Section.

    The CSV concatenates each section's header row with its data rows, with no
    section identifier column. Sections are identified by the fields they contain.

    Typical structure:
        "ClientAccountID","CurrencyPrimary","Name"
        "U1234567","USD","Matthew J Black"
        "CurrencyPrimary","StartingCash",...,"EndingCash","EndingSettledCash",...
        "USD","12345.67",...
        "CurrencyPrimary","AssetClass","SubCategory","Symbol","Quantity",...
        "USD","STK","COMMON","AAPL","10",...

    Args:
        raw:  Raw CSV report contents

    Returns:
        Mapping of normalised section name to a Section of headers and data rows
    '''
    sections: dict[str, Section] = {}
    current: Section | None = None

    for row in csv.reader(io.StringIO(raw)):
        if not row:
            continue

        normalised = [_norm(v) for v in row]
        section_name = next((name for name, sig in SECTION_SIGNATURES.items() if sig in normalised), None)

        if section_name:
            current = sections.setdefault(section_name, Section())
            current.headers = [v.strip() for v in row]
        elif current is not None:
            current.rows.append([v.strip() for v in row])

    return sections


def extract_portfolio(sections: dict[str, Section]) -> Portfolio:
    '''
    Extract positions and cash balances from parsed Flex report sections

    Args:
        sections:  Mapping of section name to Section, from parse_sections

    Returns:
        A Portfolio of positions and cash balances
    '''
    positions: list[Position] = []
    if open_positions := sections.get('openpositions'):
        for row in open_positions.rows:
            d = {_norm(h): v for h, v in zip(open_positions.headers, row)}
            positions.append(
                Position(
                    symbol=d.get('symbol'),
                    description=d.get('description'),
                    asset_class=d.get('assetclass'),
                    sub_category=d.get('subcategory'),
                    conid=d.get('conid'),
                    quantity=_parse_float(d.get('quantity', '')),
                    mark_price=_parse_float(d.get('markprice', '')),
                    position_value=_parse_float(d.get('positionvalue', '')),
                    cost_basis_price=_parse_float(d.get('costbasisprice', '')),
                    cost_basis_money=_parse_float(d.get('costbasismoney', '')),
                    fifo_pnl_unrealized=_parse_float(d.get('fifopnlunrealized', '')),
                    currency=d.get('currencyprimary'),
                )
            )

    cash: list[CashBalance] = []
    if cash_report := sections.get('cashreport'):
        for row in cash_report.rows:
            d = {_norm(h): v for h, v in zip(cash_report.headers, row)}
            ccy = d.get('currencyprimary')
            if ccy and ccy != 'BASE_SUMMARY':
                cash.append(
                    CashBalance(
                        currency=ccy,
                        ending_cash=_parse_float(d.get('endingcash', '')),
                        ending_settled_cash=_parse_float(d.get('endingsettledcash', '')),
                    )
                )

    return Portfolio(fetched_at=now_aest(), positions=positions, cash=cash)


def _parse_float(val: str) -> float | None:
    'Return float or None for blank/invalid values'
    try:
        return float(val) if val.strip() else None
    except ValueError:
        return None


def build_dataframe(portfolio: Portfolio) -> pd.DataFrame:
    'Build a dataframe of positions and cash balances for rendering'
    rows = [
        {
            'type': 'position',
            'symbol': p.symbol,
            'quantity': p.quantity,
            'mark_price': p.mark_price,
            'position_value': p.position_value,
            'cost_basis_price': p.cost_basis_price,
            'fifo_pnl_unrealized': p.fifo_pnl_unrealized,
            'currency': p.currency,
            'ending_cash': None,
            'ending_settled_cash': None,
        }
        for p in portfolio.positions
    ]

    rows.extend(
        {
            'type': 'cash',
            'symbol': None,
            'quantity': None,
            'mark_price': None,
            'position_value': None,
            'cost_basis_price': None,
            'fifo_pnl_unrealized': None,
            'currency': c.currency,
            'ending_cash': c.ending_cash,
            'ending_settled_cash': c.ending_settled_cash,
        }
        for c in portfolio.cash
    )

    return pd.DataFrame(rows).fillna('')


def write_to_gsheet(portfolio: Portfolio):
    '''
    Write the latest positions into the Symbol/Quantity/MarkPrice/CostBasisPrice columns
    of the Current sheet, replacing whatever was rendered there previously.

    Totals (row 1) and the computed columns (E-H) are left untouched.
    '''
    gsuite_creds = os.environ.get('GSUITE_OAUTH_CREDS')
    if not gsuite_creds:
        logger.error('No Google service account credentials')
        return

    gc = gspread.service_account(filename=gsuite_creds)
    worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

    # Clear the previous contents of columns A-D, below the totals row
    worksheet.batch_clear(['A3:D'])

    rows: list[list[str | float | None]] = [
        list(CURRENT_COLUMNS),
        *[[p.symbol, p.quantity, p.mark_price, p.cost_basis_price] for p in portfolio.positions],
    ]
    worksheet.update(values=rows, range_name='A3', value_input_option=ValueInputOption.user_entered)
    logger.debug('Wrote %d positions to gsheet', len(portfolio.positions))


@click.group(name='ibkr')
def cli():
    'IBKR portfolio poller via the Flex Web Service'


@cli.command
def summary(plugin: InformaPlugin):
    'Show the last fetched portfolio'
    state = cast('State', plugin.load_state())
    if state.portfolio is None:
        click.echo('Never fetched')
        return

    pretty.dataframe(
        build_dataframe(state.portfolio),
        title=f'Fetched {state.portfolio.fetched_at.isoformat()}',
    )
