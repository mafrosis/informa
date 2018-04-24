import pytest

@pytest.fixture
def redis_data():
    """
    Return bytestring representing contents of Redis timeseries
    """
    base = 1524599000
    return ''.join(['{}22.255.5'.format(base+x) for x in range(0, 60*60, 60)]).encode()
