from unittest.mock import patch

import requests

from informa.plugins.external_ip import State, fetch_external_ip, main, update_dns_record


@patch('requests.get')
def test_fetch_external_ip(mock_requests_get):
    '''
    Ensure the external IP is parsed from the ipify response
    '''
    mock_requests_get.return_value.status_code = 200
    mock_requests_get.return_value.json.return_value = {'ip': '1.2.3.4'}

    assert fetch_external_ip() == '1.2.3.4'


@patch('requests.get')
def test_fetch_external_ip_returns_none_on_http_error(mock_requests_get):
    '''
    Ensure None is returned when ipify is unreachable
    '''
    import requests

    mock_requests_get.return_value.raise_for_status.side_effect = requests.RequestException

    assert fetch_external_ip() is None


@patch.dict('os.environ', {'GANDI_API_KEY': 'test-key'})
@patch('requests.put')
def test_update_dns_record_success(mock_requests_put):
    '''
    Ensure True is returned when Gandi accepts the record update
    '''
    mock_requests_put.return_value.raise_for_status.return_value = None

    assert update_dns_record('1.2.3.4') is True


@patch.dict('os.environ', {'GANDI_API_KEY': 'test-key'})
@patch('requests.put')
def test_update_dns_record_failure(mock_requests_put):
    '''
    Ensure False is returned when the Gandi API fails
    '''
    mock_requests_put.return_value.raise_for_status.side_effect = requests.HTTPError

    assert update_dns_record('1.2.3.4') is False


@patch('informa.plugins.external_ip.update_dns_record', return_value=True)
@patch('informa.plugins.external_ip.fetch_external_ip')
def test_main_updates_when_ip_changed(mock_fetch_ip, mock_update):
    '''
    Ensure DNS is updated and count 1 returned when the IP has changed
    '''
    mock_fetch_ip.return_value = '5.6.7.8'

    state = State(ip='1.2.3.4')
    assert main(state) == 1
    assert state.ip == '5.6.7.8'


@patch('informa.plugins.external_ip.update_dns_record')
@patch('informa.plugins.external_ip.fetch_external_ip')
def test_main_skips_when_ip_unchanged(mock_fetch_ip, mock_update):
    '''
    Ensure no API call is made when the external IP is unchanged
    '''
    mock_fetch_ip.return_value = '1.2.3.4'

    state = State(ip='1.2.3.4')
    assert main(state) == 0
    mock_update.assert_not_called()
