import datetime
import os
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from informa.plugins.ibkr import (
    CURRENT_COLUMNS,
    CashBalance,
    Config,
    FlexQueryError,
    Portfolio,
    Position,
    State,
    build_dataframe,
    extract_portfolio,
    get_statement,
    main,
    parse_sections,
    send_request,
    write_to_gsheet,
)

SEND_SUCCESS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<FlexQueryResponse><Status>Success</Status><ReferenceCode>1234567</ReferenceCode></FlexQueryResponse>'
)
SEND_FAIL = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<FlexQueryResponse><Status>fail</Status><ErrorMessage>invalid token</ErrorMessage></FlexQueryResponse>'
)


@pytest.fixture
def amzn_position():
    return Position(
        symbol='AMZN',
        description='AMAZON.COM INC',
        asset_class='STK',
        sub_category='COMMON',
        conid='3691937',
        quantity=10.0,
        mark_price=100.5,
        position_value=1005.0,
        cost_basis_price=80.0,
        cost_basis_money=800.0,
        fifo_pnl_unrealized=205.0,
        currency='USD',
    )


@pytest.fixture
def portfolio(amzn_position):
    return Portfolio(
        fetched_at=datetime.datetime(2026, 9, 17, 9, 30, 0, tzinfo=ZoneInfo('Australia/Melbourne')),
        positions=[amzn_position],
        cash=[CashBalance(currency='AUD', ending_cash=350.5, ending_settled_cash=350.5)],
    )


@patch('requests.get')
def test_ibkr_send_request(mock_get):
    mock_get.return_value = Mock(text=SEND_SUCCESS)

    assert send_request('token', 'query_id') == '1234567'


@patch('requests.get')
def test_ibkr_send_request_failure(mock_get):
    mock_get.return_value = Mock(text=SEND_FAIL)

    with pytest.raises(FlexQueryError):
        send_request('token', 'query_id')


@patch('informa.plugins.ibkr.time.sleep')
@patch('requests.get')
def test_ibkr_get_statement_retries(mock_get, mock_sleep, http_response):
    raw = http_response('ibkr')
    mock_get.side_effect = [Mock(text=SEND_FAIL), Mock(text=SEND_FAIL), Mock(text=raw)]

    assert get_statement('token', 'ref') == raw
    assert mock_sleep.call_count == 2


@patch('informa.plugins.ibkr.time.sleep')
@patch('requests.get')
def test_ibkr_get_statement_exhausts_retries(mock_get, mock_sleep):
    mock_get.side_effect = [Mock(text=SEND_FAIL)] * 5

    with pytest.raises(FlexQueryError):
        get_statement('token', 'ref')
    assert mock_sleep.call_count == 4


def test_ibkr_parse_sections(http_response):
    sections = parse_sections(http_response('ibkr'))

    assert set(sections) == {'accountinformation', 'cashreport', 'openpositions'}
    assert sections['openpositions'].headers[0] == 'CurrencyPrimary'
    assert len(sections['openpositions'].rows) == 2
    assert len(sections['cashreport'].rows) == 3
    assert len(sections['accountinformation'].rows) == 1


def test_ibkr_extract_portfolio(http_response):
    portfolio = extract_portfolio(parse_sections(http_response('ibkr')))

    assert len(portfolio.positions) == 2
    assert len(portfolio.cash) == 2  # BASE_SUMMARY row is filtered

    amzn = portfolio.positions[0]
    assert amzn.symbol == 'AMZN'
    assert amzn.asset_class == 'STK'
    assert amzn.sub_category == 'COMMON'
    assert amzn.conid == '3691937'
    assert amzn.quantity == 10.0
    assert amzn.mark_price == 100.5
    assert amzn.position_value == 1005.0
    assert amzn.cost_basis_price == 80.0
    assert amzn.cost_basis_money == 800.0
    assert amzn.fifo_pnl_unrealized == 205.0
    assert amzn.currency == 'USD'

    assert portfolio.cash[0].currency == 'AUD'
    assert portfolio.cash[0].ending_cash == 350.5
    assert portfolio.cash[0].ending_settled_cash == 350.5

    assert portfolio.fetched_at is not None


@patch('informa.plugins.ibkr.write_to_gsheet')
@patch('informa.plugins.ibkr.get_statement')
@patch('informa.plugins.ibkr.send_request')
def test_ibkr_main(mock_send_request, mock_get_statement, mock_write, http_response):
    mock_send_request.return_value = '1234567'
    mock_get_statement.return_value = http_response('ibkr')

    state = State()
    with patch.dict(os.environ, {'IBKR_FLEX_TOKEN': 't'}):
        assert main(state, Config(query_id='q')) == 4

    assert state.portfolio is not None
    assert len(state.portfolio.positions) == 2
    assert len(state.portfolio.cash) == 2
    mock_send_request.assert_called_once_with('t', 'q')
    mock_write.assert_called_once()


@patch('requests.get')
def test_ibkr_main_missing_env(mock_get):
    with patch.dict(os.environ, {}, clear=True):
        assert main(State(), Config(query_id='q')) == 0

    mock_get.assert_not_called()


@patch('informa.plugins.ibkr.write_to_gsheet')
@patch('informa.plugins.ibkr.get_statement')
@patch('informa.plugins.ibkr.send_request')
def test_ibkr_main_empty_statement(mock_send_request, mock_get_statement, mock_write):
    mock_send_request.return_value = '1234567'
    mock_get_statement.return_value = 'FlexQuery,Header,QueryName\nFlexQuery,Data,test\n'

    state = State()
    with patch.dict(os.environ, {'IBKR_FLEX_TOKEN': 't'}):
        assert main(state, Config(query_id='q')) == 0

    assert state.portfolio is None
    mock_write.assert_not_called()


@patch('informa.plugins.ibkr.get_statement')
@patch('informa.plugins.ibkr.send_request')
def test_ibkr_main_xml_statement(mock_send_request, mock_get_statement):
    'The query template must be configured to deliver TEXT (CSV), not XML'
    mock_send_request.return_value = '1234567'
    mock_get_statement.return_value = '<FlexQueryResponse queryName="DailyPortfolio" type="AF"></FlexQueryResponse>'

    with patch.dict(os.environ, {'IBKR_FLEX_TOKEN': 't'}), pytest.raises(FlexQueryError):
        main(State(), Config(query_id='q'))


def test_ibkr_build_dataframe(portfolio, amzn_position):
    df = build_dataframe(portfolio)

    assert len(df) == 2
    assert list(df.columns) == [
        'type',
        'symbol',
        'quantity',
        'mark_price',
        'position_value',
        'cost_basis_price',
        'fifo_pnl_unrealized',
        'currency',
        'ending_cash',
        'ending_settled_cash',
    ]

    position = df.iloc[0]
    assert position['type'] == 'position'
    assert position['symbol'] == 'AMZN'
    assert position['quantity'] == 10.0
    assert position['mark_price'] == 100.5
    assert position['position_value'] == 1005.0
    assert position['cost_basis_price'] == 80.0
    assert position['fifo_pnl_unrealized'] == 205.0
    assert position['currency'] == 'USD'
    assert position['ending_cash'] == ''

    cash = df.iloc[1]
    assert cash['type'] == 'cash'
    assert cash['symbol'] == ''
    assert cash['currency'] == 'AUD'
    assert cash['ending_cash'] == 350.5
    assert cash['ending_settled_cash'] == 350.5


@patch('informa.plugins.ibkr.gspread')
def test_ibkr_write_to_gsheet(mock_gspread, portfolio):
    worksheet = mock_gspread.service_account.return_value.open_by_key.return_value.worksheet.return_value

    with patch.dict(os.environ, {'GSUITE_OAUTH_CREDS': '/creds.json'}):
        write_to_gsheet(portfolio)

    # Columns A-D are cleared from below the totals row, then re-written
    worksheet.batch_clear.assert_called_once_with(['A3:D'])

    kwargs = worksheet.update.call_args.kwargs
    assert kwargs['range_name'] == 'A3'
    assert kwargs['value_input_option'] == 'USER_ENTERED'
    assert kwargs['values'] == [
        list(CURRENT_COLUMNS),
        ['AMZN', 10.0, 100.5, 80.0],
    ]


@patch('informa.plugins.ibkr.gspread')
def test_ibkr_write_to_gsheet_missing_creds(mock_gspread, portfolio):
    with patch.dict(os.environ, {}, clear=True):
        write_to_gsheet(portfolio)

    mock_gspread.service_account.assert_not_called()
