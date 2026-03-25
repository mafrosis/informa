import os

import pytest
from click.testing import CliRunner


@pytest.fixture
def http_response():
    def _http_response(plugin):
        with open(f'test/fixtures/{plugin}.txt', encoding='utf8') as f:
            return f.read()

    return _http_response


@pytest.fixture
def runner():
    return CliRunner(env={**os.environ, 'LOCAL': ''})
