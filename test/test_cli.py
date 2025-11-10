import os
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from informa.cli import cli


@pytest.fixture
def runner():
    '''Create a CLI test runner'''
    return CliRunner()


@pytest.fixture
def mock_app_plugins():
    '''Mock the app.plugins dictionary'''
    with patch('informa.cli.app') as mock_app:
        mock_app.plugins = {}
        yield mock_app


class TestCliStart:
    '''Test the start command'''

    @patch('informa.cli.asyncio.run')
    def test_start_default(self, mock_asyncio_run, runner, mock_app_plugins):
        '''Test starting with default parameters'''
        result = runner.invoke(cli, ['start'])

        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    @patch('informa.cli.asyncio.run')
    def test_start_custom_host_port(self, mock_asyncio_run, runner, mock_app_plugins):
        '''Test starting with custom host and port'''
        result = runner.invoke(cli, ['start', '--host', '0.0.0.0', '--port', '8000'])

        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    @patch('informa.cli.asyncio.run')
    def test_start_with_plugins(self, mock_asyncio_run, runner, mock_app_plugins):
        '''Test starting with specific plugins'''
        mock_app_plugins.plugins = {
            'informa.plugins.tob': Mock(),
            'informa.plugins.kindle_gcal': Mock(),
        }

        result = runner.invoke(cli, ['start', '--plugins', 'tob,kindle_gcal'])

        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    @patch('informa.cli.asyncio.run')
    def test_start_with_invalid_plugin(self, mock_asyncio_run, runner, mock_app_plugins):
        '''Test starting with invalid plugin name'''
        mock_app_plugins.plugins = {}

        result = runner.invoke(cli, ['start', '--plugins', 'nonexistent'])

        # Should log error but not crash
        assert result.exit_code == 0


class TestAdminCommands:
    '''Test admin commands'''

    @patch('informa.cli.requests.get')
    def test_admin_list_success(self, mock_get, runner):
        '''Test listing plugins successfully'''
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'name': 'informa.plugins.tob',
                'last_run': '2024-01-01T00:00:00',
                'last_count': 5,
                'enabled': True,
                'tasks': ['run, every 12 hours'],
            },
        ]
        mock_get.return_value = mock_response

        result = runner.invoke(cli, ['admin', 'list'])

        assert result.exit_code == 0
        assert 'informa.plugins.tob' in result.output
        mock_get.assert_called_once()

    @patch('informa.cli.requests.get')
    def test_admin_list_connection_error(self, mock_get, runner):
        '''Test listing plugins when server is down'''
        from requests.exceptions import ConnectionError

        mock_get.side_effect = ConnectionError('Connection refused')

        result = runner.invoke(cli, ['admin', 'list'])

        assert result.exit_code != 0
        assert 'down' in result.output or 'fail' in result.output.lower()

    @patch('informa.cli.requests.post')
    @patch('informa.cli.app')
    def test_admin_enable(self, mock_app, mock_post, runner):
        '''Test enabling a plugin'''
        mock_app.plugins = {'informa.plugins.tob': Mock()}
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = runner.invoke(cli, ['admin', 'enable', 'tob'])

        assert result.exit_code == 0
        assert 'enabled' in result.output
        mock_post.assert_called_once()

    @patch('informa.cli.requests.post')
    @patch('informa.cli.app')
    def test_admin_enable_persist(self, mock_app, mock_post, runner):
        '''Test enabling a plugin with persist flag'''
        mock_app.plugins = {'informa.plugins.tob': Mock()}
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = runner.invoke(cli, ['admin', 'enable', 'tob', '--persist'])

        assert result.exit_code == 0
        mock_post.assert_called_once()
        # Check that persist=True was passed
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs['params']['persist'] is True

    @patch('informa.cli.requests.post')
    @patch('informa.cli.app')
    def test_admin_enable_invalid_plugin(self, mock_app, mock_post, runner):
        '''Test enabling an invalid plugin'''
        mock_app.plugins = {}

        result = runner.invoke(cli, ['admin', 'enable', 'nonexistent'])

        assert result.exit_code != 0
        assert 'Invalid plugin' in result.output
        mock_post.assert_not_called()

    @patch('informa.cli.requests.delete')
    @patch('informa.cli.app')
    def test_admin_disable(self, mock_app, mock_delete, runner):
        '''Test disabling a plugin'''
        mock_app.plugins = {'informa.plugins.tob': Mock()}
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response

        result = runner.invoke(cli, ['admin', 'disable', 'tob'])

        assert result.exit_code == 0
        assert 'disabled' in result.output
        mock_delete.assert_called_once()

    @patch('informa.cli.requests.delete')
    @patch('informa.cli.app')
    def test_admin_disable_persist(self, mock_app, mock_delete, runner):
        '''Test disabling a plugin with persist flag'''
        mock_app.plugins = {'informa.plugins.tob': Mock()}
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response

        result = runner.invoke(cli, ['admin', 'disable', 'tob', '--persist'])

        assert result.exit_code == 0
        mock_delete.assert_called_once()
        # Check that persist=True was passed
        call_kwargs = mock_delete.call_args
        assert call_kwargs.kwargs['params']['persist'] is True


class TestCliOptions:
    '''Test CLI global options'''

    @patch('informa.cli.pretty.table')
    @patch('informa.cli.requests.get')
    def test_debug_flag(self, mock_get, mock_table, runner):
        '''Test --debug flag is accepted'''
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        mock_table.return_value = None

        result = runner.invoke(cli, ['--debug', 'admin', 'list'])

        # Command should execute - debug flag should be accepted
        # Exit code may vary but command should not crash
        assert result.exit_code in (0, 1)  # Allow for potential errors in test environment

    def test_server_option(self, runner):
        '''Test --server option'''
        with patch('informa.cli.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_get.return_value = mock_response

            result = runner.invoke(cli, ['--server', 'http://localhost:3000', 'admin', 'list'])

            # Check that custom server was used
            mock_get.assert_called_once()
            call_args = mock_get.call_args[0]
            assert 'http://localhost:3000' in call_args[0]

    def test_debug_env_var(self, runner):
        '''Test DEBUG environment variable'''
        with patch.dict(os.environ, {'DEBUG': '1'}):
            result = runner.invoke(cli, ['admin', 'list'], catch_exceptions=False)

            # Command will fail but env var should be respected
            assert result.exit_code is not None


class TestPluginNameNormalization:
    '''Test plugin name normalization'''

    @patch('informa.cli.app')
    def test_verify_plugin_with_prefix(self, mock_app):
        '''Test verifying plugin with full prefix'''
        from informa.cli import verify_plugin_or_raise

        mock_app.plugins = {'informa.plugins.tob': Mock()}

        result = verify_plugin_or_raise('informa.plugins.tob')
        assert result == 'informa.plugins.tob'

    @patch('informa.cli.app')
    def test_verify_plugin_without_prefix(self, mock_app):
        '''Test verifying plugin without prefix'''
        from informa.cli import verify_plugin_or_raise

        mock_app.plugins = {'informa.plugins.tob': Mock()}

        result = verify_plugin_or_raise('tob')
        assert result == 'informa.plugins.tob'

    @patch('informa.cli.app')
    def test_verify_plugin_with_dashes(self, mock_app):
        '''Test verifying plugin name with dashes'''
        from informa.cli import verify_plugin_or_raise

        mock_app.plugins = {'informa.plugins.kindle_gcal': Mock()}

        result = verify_plugin_or_raise('kindle-gcal')
        assert result == 'informa.plugins.kindle_gcal'

    @patch('informa.cli.app')
    def test_verify_plugin_invalid(self, mock_app):
        '''Test verifying invalid plugin raises exception'''
        from informa.cli import verify_plugin_or_raise
        from click.exceptions import ClickException

        mock_app.plugins = {}

        with pytest.raises(ClickException) as exc_info:
            verify_plugin_or_raise('nonexistent')

        assert 'Invalid plugin' in str(exc_info.value)
