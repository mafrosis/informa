import collections
import datetime

from unittest.mock import patch

from informa.lib.redis import TempHumidRedis


@patch('informa.lib.redis.redis')
def test_constructor(mock_redis):
    tsr = TempHumidRedis('localhost', 9999)
    mock_redis.StrictRedis.assert_called_with('localhost', 9999)


@patch('informa.lib.redis.datetime')
@patch('informa.lib.redis.redis')
def test_set_called_with_correct_params(mock_redis, mock_datetime):
    mock_datetime.date.today.return_value = datetime.date(2018, 4, 24)
    mock_datetime.datetime.now.return_value.timestamp.return_value = 1524559470.123456

    tsr = TempHumidRedis('localhost', 9999)
    tsr.append(22.2, 55.5)

    mock_redis.StrictRedis.return_value.append.assert_called_with('180424', '152455947022.255.5')


@patch('informa.lib.redis.datetime')
@patch('informa.lib.redis.redis')
def test_sub_ten_value_is_padded_correctly(mock_redis, mock_datetime):
    mock_datetime.date.today.return_value = datetime.date(2018, 4, 24)
    mock_datetime.datetime.now.return_value.timestamp.return_value = 1524559470.123456

    tsr = TempHumidRedis('localhost', 9999)
    tsr.append(22.2, 5.5)

    # note padded zero in stored string
    mock_redis.StrictRedis.return_value.append.assert_called_with('180424', '152455947022.205.5')


@patch('informa.lib.redis.redis')
def test_get_day_decodes_to_dict(mock_redis, redis_data):
    mock_redis.StrictRedis.return_value.get.return_value = redis_data

    tsr = TempHumidRedis('localhost', 9999)
    data = tsr.get_day('180423')

    assert type(data) is collections.OrderedDict
    assert list(data.keys())[0] == 1524599000
    assert list(data.keys())[-1] == 1524602540
