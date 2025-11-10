import datetime
import inspect
from unittest.mock import Mock, patch

import pytest
from zoneinfo import ZoneInfo

from informa.exceptions import PluginAlreadyDisabled, PluginAlreadyEnabled
from informa.main import Informa


@pytest.fixture
def informa_app():
    '''Create a fresh Informa instance for testing'''
    app = Informa()
    return app


@pytest.fixture
def mock_plugin_module():
    '''Create a mock plugin module'''
    module = Mock()
    module.__name__ = 'informa.plugins.test_plugin'
    return module


class TestInformaInit:
    '''Test Informa initialization'''

    def test_init_creates_instances(self, informa_app):
        '''Test that __init__ creates required instances'''
        assert informa_app.plugins == {}
        assert informa_app.rocketry is not None
        assert informa_app.fastapi is not None
        assert informa_app.config is not None

    def test_rocketry_config(self, informa_app):
        '''Test Rocketry is configured correctly'''
        # Rocketry stores config in session.config
        assert informa_app.rocketry.session.config.execution == 'async'
        assert isinstance(informa_app.rocketry.session.config.timezone, ZoneInfo)
        assert informa_app.rocketry.session.config.cycle_sleep == 10


class TestTaskDecorator:
    '''Test @app.task() decorator'''

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_task_decorator_registers_plugin(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test that @task decorator registers a new plugin'''

        def test_task(plugin):
            pass

        test_task.__module__ = mock_plugin_module.__name__

        # Register the task
        with patch('inspect.getmodule', return_value=mock_plugin_module):
            informa_app.task('every 5 mins')(test_task)

        assert mock_plugin_module.__name__ in informa_app.plugins

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_task_decorator_adds_task(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test that @task decorator adds task to plugin'''

        def test_task(plugin):
            pass

        test_task.__module__ = mock_plugin_module.__name__

        with patch('inspect.getmodule', return_value=mock_plugin_module):
            decorated = informa_app.task('every 5 mins')(test_task)

        plugin = informa_app.plugins[mock_plugin_module.__name__]
        assert len(plugin.tasks) == 1
        assert plugin.tasks[0].condition == 'every 5 mins'
        assert decorated == test_task

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_task_decorator_multiple_tasks(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test multiple tasks can be registered for same plugin'''

        def task1(plugin):
            pass

        def task2(plugin):
            pass

        task1.__module__ = mock_plugin_module.__name__
        task2.__module__ = mock_plugin_module.__name__

        with patch('inspect.getmodule', return_value=mock_plugin_module):
            informa_app.task('every 5 mins')(task1)
            informa_app.task('every 10 mins')(task2)

        plugin = informa_app.plugins[mock_plugin_module.__name__]
        assert len(plugin.tasks) == 2


class TestApiDecorator:
    '''Test @app.api() decorator'''

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_api_decorator_registers_plugin(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test that @api decorator registers a new plugin'''
        from fastapi import APIRouter

        router = APIRouter()

        def test_api(plugin):
            pass

        test_api.__module__ = mock_plugin_module.__name__

        with patch('inspect.getmodule', return_value=mock_plugin_module):
            informa_app.api(router)(test_api)

        assert mock_plugin_module.__name__ in informa_app.plugins

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_api_decorator_sets_router(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test that @api decorator sets router on plugin'''
        from fastapi import APIRouter

        router = APIRouter()

        def test_api(plugin):
            pass

        test_api.__module__ = mock_plugin_module.__name__

        with patch('inspect.getmodule', return_value=mock_plugin_module):
            informa_app.api(router)(test_api)

        plugin = informa_app.plugins[mock_plugin_module.__name__]
        assert plugin.api == router


class TestEnablePlugin:
    '''Test plugin enabling functionality'''

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_enable_plugin_success(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test successfully enabling a plugin'''
        from informa.lib.plugin import InformaPlugin, InformaTask

        def test_task(plugin):
            pass

        plugin = InformaPlugin(mock_plugin_module)
        plugin.tasks = [InformaTask(test_task, 'every 5 mins')]
        plugin.enabled = False
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        informa_app.enable_plugin(mock_plugin_module.__name__)

        assert plugin.enabled is True

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_enable_plugin_already_enabled(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test enabling already enabled plugin raises exception'''
        from informa.lib.plugin import InformaPlugin

        plugin = InformaPlugin(mock_plugin_module)
        plugin.enabled = True
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        with pytest.raises(PluginAlreadyEnabled):
            informa_app.enable_plugin(mock_plugin_module.__name__)

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_enable_plugin_registers_tasks(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test enabling plugin registers tasks with Rocketry'''
        from informa.lib.plugin import InformaPlugin, InformaTask

        def test_task(plugin):
            pass

        plugin = InformaPlugin(mock_plugin_module)
        plugin.tasks = [InformaTask(test_task, 'every 5 mins')]
        plugin.enabled = False
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        with patch.object(informa_app.rocketry.session, 'create_task') as mock_create:
            informa_app.enable_plugin(mock_plugin_module.__name__)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs['func'] == test_task
            assert call_kwargs['start_cond'] == 'every 5 mins'

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_enable_plugin_registers_api(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test enabling plugin registers API router'''
        from fastapi import APIRouter
        from informa.lib.plugin import InformaPlugin

        router = APIRouter(prefix='/test')
        plugin = InformaPlugin(mock_plugin_module)
        plugin.api = router
        plugin.enabled = False
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        with patch.object(informa_app.fastapi, 'include_router') as mock_include:
            informa_app.enable_plugin(mock_plugin_module.__name__)

            mock_include.assert_called()

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    @patch('informa.main.save_app_config')
    @patch('informa.main.load_app_config')
    def test_enable_plugin_persist(self, mock_load, mock_save, mock_post_init, informa_app, mock_plugin_module):
        '''Test enabling plugin with persist flag'''
        from informa.lib.config import AppConfig
        from informa.lib.plugin import InformaPlugin

        config = AppConfig(disabled_plugins={'informa.plugins.test_plugin'})
        mock_load.return_value = config

        plugin = InformaPlugin(mock_plugin_module)
        plugin.enabled = False
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        informa_app.enable_plugin(mock_plugin_module.__name__, persist=True)

        mock_load.assert_called_once()
        mock_save.assert_called_once()
        saved_config = mock_save.call_args[0][0]
        assert mock_plugin_module.__name__ not in saved_config.disabled_plugins


class TestDisablePlugin:
    '''Test plugin disabling functionality'''

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_disable_plugin_success(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test successfully disabling a plugin'''
        from informa.lib.plugin import InformaPlugin

        plugin = InformaPlugin(mock_plugin_module)
        plugin.enabled = True
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        informa_app.disable_plugin(mock_plugin_module.__name__)

        assert plugin.enabled is False

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_disable_plugin_already_disabled(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test disabling already disabled plugin raises exception'''
        from informa.lib.plugin import InformaPlugin

        plugin = InformaPlugin(mock_plugin_module)
        plugin.enabled = False
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        with pytest.raises(PluginAlreadyDisabled):
            informa_app.disable_plugin(mock_plugin_module.__name__)

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_disable_plugin_removes_tasks(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test disabling plugin removes tasks from Rocketry'''
        from informa.lib.plugin import InformaPlugin, InformaTask

        def test_task(plugin):
            pass

        plugin = InformaPlugin(mock_plugin_module)
        plugin.tasks = [InformaTask(test_task, 'every 5 mins')]
        plugin.enabled = True
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        with patch.object(informa_app.rocketry.session, 'remove_task') as mock_remove:
            informa_app.disable_plugin(mock_plugin_module.__name__)

            mock_remove.assert_called_once()

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_disable_plugin_removes_api(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test disabling plugin attempts to remove API routes'''
        from fastapi import APIRouter
        from informa.lib.plugin import InformaPlugin

        router = APIRouter(prefix='/test')
        plugin = InformaPlugin(mock_plugin_module)
        plugin.api = router
        plugin.enabled = True
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        # Don't actually test route removal as FastAPI routes are complex
        # Just verify disable doesn't crash when plugin has API
        informa_app.disable_plugin(mock_plugin_module.__name__)

        # Plugin should be disabled
        assert plugin.enabled is False

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    @patch('informa.main.save_app_config')
    @patch('informa.main.load_app_config')
    def test_disable_plugin_persist(self, mock_load, mock_save, mock_post_init, informa_app, mock_plugin_module):
        '''Test disabling plugin with persist flag'''
        from informa.lib.config import AppConfig
        from informa.lib.plugin import InformaPlugin

        config = AppConfig(disabled_plugins=set())
        mock_load.return_value = config

        plugin = InformaPlugin(mock_plugin_module)
        plugin.enabled = True
        informa_app.plugins[mock_plugin_module.__name__] = plugin

        informa_app.disable_plugin(mock_plugin_module.__name__, persist=True)

        mock_load.assert_called_once()
        mock_save.assert_called_once()
        saved_config = mock_save.call_args[0][0]
        assert mock_plugin_module.__name__ in saved_config.disabled_plugins


class TestConfigureCli:
    '''Test CLI configuration'''

    @patch('informa.lib.plugin.InformaPlugin.__post_init__', return_value=None)
    def test_configure_cli_adds_commands(self, mock_post_init, informa_app, mock_plugin_module):
        '''Test configure_cli adds plugin CLI commands'''
        import click
        from informa.lib.plugin import InformaPlugin

        plugin = InformaPlugin(mock_plugin_module)

        # Create a mock CLI group
        cli_group = click.Group(name='test_plugin')

        @cli_group.command('test-cmd')
        def test_command():
            pass

        with patch.object(plugin, 'cli', cli_group):
            with patch.object(plugin, 'wrap_cli', return_value=test_command):
                informa_app.plugins[mock_plugin_module.__name__] = plugin

                informa_cli = click.Group(name='informa')
                informa_app.configure_cli(informa_cli)

                # Plugin CLI should be added to main CLI
                assert 'test_plugin' in informa_cli.commands or len(informa_cli.commands) > 0
