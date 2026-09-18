import os
from pathlib import Path
from unittest.mock import patch

import pytest

from informa.plugins.westpac_statements import State, main, process_statement

DUMMY_PDF = b'%PDF-1.4\n%dummy statement, content is not read by these tests\n'


@pytest.fixture
def statements_dir(tmp_path):
    'Create a statements directory containing a single statement PDF'
    (tmp_path / '2512.pdf').write_bytes(DUMMY_PDF)
    return tmp_path


@patch('informa.plugins.westpac_statements.mailgun.send')
@patch('informa.plugins.westpac_statements.westpac.cc')
def test_main_imports_new_statements(mock_cc, mock_mailgun, statements_dir):
    state = State()
    with patch.dict(os.environ, {'WESTPAC_STATEMENTS_DIR': str(statements_dir)}):
        assert main(state) == 1

    mock_cc.assert_called_once()
    mock_mailgun.assert_called_once()
    assert mock_mailgun.call_args[0][1] == 'Westpac statement 2512.pdf imported'
    assert state.imported == ['2512.pdf']


@patch('informa.plugins.westpac_statements.mailgun.send')
@patch('informa.plugins.westpac_statements.westpac.cc')
def test_main_skips_already_imported(mock_cc, mock_mailgun, statements_dir):
    state = State(imported=['2512.pdf'])
    with patch.dict(os.environ, {'WESTPAC_STATEMENTS_DIR': str(statements_dir)}):
        assert main(state) == 0

    mock_cc.assert_not_called()
    mock_mailgun.assert_not_called()


@patch('informa.plugins.westpac_statements.mailgun.send')
@patch('informa.plugins.westpac_statements.westpac.cc')
def test_main_processes_multiple_statements_oldest_first(mock_cc, mock_mailgun, statements_dir):
    for name in ('2601.pdf', '2511.pdf'):
        (statements_dir / name).write_bytes(DUMMY_PDF)

    state = State()
    with patch.dict(os.environ, {'WESTPAC_STATEMENTS_DIR': str(statements_dir)}):
        assert main(state) == 3

    # Sorted oldest (2511) to newest (2601)
    imported_files = [Path(call[0][0].name).name for call in mock_cc.call_args_list]
    assert imported_files == ['2511.pdf', '2512.pdf', '2601.pdf']
    assert state.imported == ['2511.pdf', '2512.pdf', '2601.pdf']


@patch('informa.plugins.westpac_statements.westpac.cc')
def test_main_missing_directory(mock_cc):
    with patch.dict(os.environ, {'WESTPAC_STATEMENTS_DIR': '/nonexistent/path'}):
        assert main(State()) == 0

    mock_cc.assert_not_called()


@patch('informa.plugins.westpac_statements.mailgun.send')
@patch('informa.plugins.westpac_statements.westpac.cc')
def test_main_failure_not_recorded(mock_cc, mock_mailgun, statements_dir):
    mock_cc.side_effect = OSError('disk error')

    state = State()
    with patch.dict(os.environ, {'WESTPAC_STATEMENTS_DIR': str(statements_dir)}):
        assert main(state) == 0

    # Failed statement is retried on next run
    assert state.imported == []


@patch('informa.plugins.westpac_statements.mailgun.send')
@patch('informa.plugins.westpac_statements.westpac.cc')
def test_process_statement_success(mock_cc, mock_mailgun, tmp_path):
    pdf = tmp_path / '2512.pdf'
    pdf.write_bytes(DUMMY_PDF)

    assert process_statement(pdf) is True
    mock_mailgun.assert_called_once()


@patch('informa.plugins.westpac_statements.raise_alarm')
def test_process_statement_missing_file(mock_raise_alarm, tmp_path):
    assert process_statement(tmp_path / 'nope.pdf') is False
    mock_raise_alarm.assert_called_once()


def test_state_roundtrip():
    'State must survive serialisation to and from the JSON state file'
    state = State(imported=['2512.pdf', '2601.pdf'])

    data = state.to_dict()
    assert State.from_dict(data) == state
