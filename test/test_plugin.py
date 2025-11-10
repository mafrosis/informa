import datetime
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from zoneinfo import ZoneInfo

from informa.exceptions import AppError, PluginRequiresConfigError
from informa.lib import ConfigBase, PluginAdapter, StateBase
from informa.lib.plugin import InformaPlugin


@pytest.fixture
def mock_module():
    '''Create a mock plugin module'''
    module = Mock()
    module.__name__ = 'informa.plugins.test_plugin'

    # Mock logger
    from informa.lib import PluginAdapter
    import logging

    module.logger = PluginAdapter(logging.getLogger('informa'), 'test_plugin')

    return module


@pytest.fixture
def plugin_module():
    '''Create a mock plugin module'''
    module = Mock()
    module.__name__ = 'informa.plugins.test_plugin'

    # Mock logger
    module.logger = PluginAdapter(logging.getLogger('informa'), 'test_plugin')

    return module


@pytest.fixture
def test_plugin(plugin_module, temp_state_dir):
    '''Create a test plugin instance'''
    # Patch __post_init__ to avoid state loading issues
    with patch.object(InformaPlugin, '__post_init__', return_value=None):
        plugin = InformaPlugin(plugin_module)
        plugin.last_run = None
        plugin.last_count = None
    return plugin


@pytest.fixture
def temp_state_dir():
    '''Create a temporary state directory'''
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {'STATE_DIR': tmpdir}):
            yield tmpdir


@pytest.fixture
def temp_config_dir():
    '''Create a temporary config directory'''
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {'CONFIG_DIR': tmpdir}):
            yield tmpdir


class TestInformaPluginInit:
    '''Test InformaPlugin initialization'''

    def test_plugin_name(self, test_plugin):
        '''Test plugin name property'''
        assert test_plugin.name == 'informa.plugins.test_plugin'

    def test_plugin_initial_state(self, test_plugin):
        '''Test plugin starts with no tasks'''
        assert test_plugin.tasks == []
        assert test_plugin.enabled is None
        assert test_plugin.api is None


class TestStateManagement:
    '''Test plugin state loading and saving'''

    def test_load_state_new_plugin(self, test_plugin, temp_state_dir):
        '''Test loading state for new plugin creates empty state'''
        state = test_plugin.load_state()

        assert isinstance(state, StateBase)
        assert state.last_run is None
        assert state.last_count is None

    def test_write_state(self, test_plugin, temp_state_dir):
        '''Test writing state to disk'''
        state = StateBase(
            last_run=datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo('Australia/Melbourne')), last_count=5
        )

        test_plugin.write_state(state)

        state_file = Path(temp_state_dir) / 'informa.plugins.test_plugin.json'
        assert state_file.exists()

        with open(state_file, encoding='utf8') as f:
            data = json.load(f)
            assert data['last_count'] == 5
            assert '2024-01-01' in data['last_run']

    def test_load_existing_state(self, test_plugin, temp_state_dir):
        '''Test loading existing state from disk'''
        state_file = Path(temp_state_dir) / 'informa.plugins.test_plugin.json'
        state_data = {'last_run': '2024-01-01T00:00:00+11:00', 'last_count': 10}

        with open(state_file, 'w', encoding='utf8') as f:
            json.dump(state_data, f)

        state = test_plugin.load_state()

        assert state.last_count == 10
        assert state.last_run is not None

    def test_write_state_with_custom_types(self, test_plugin, temp_state_dir):
        '''Test writing state with custom types like Decimal and set'''

        @dataclass
        class CustomState(StateBase):
            amounts: list[Decimal] = field(default_factory=list)
            tags: set[str] = field(default_factory=set)

        with patch.object(test_plugin, 'state_cls', CustomState):
            state = CustomState(amounts=[Decimal('10.50'), Decimal('20.75')], tags={'tag1', 'tag2'})

            test_plugin.write_state(state)

            state_file = Path(temp_state_dir) / 'informa.plugins.test_plugin.json'
            assert state_file.exists()


class TestConfigManagement:
    '''Test plugin config loading'''

    def test_load_config_no_config_class(self, test_plugin, temp_config_dir):
        '''Test loading config when plugin has no config class'''
        with patch.object(test_plugin, 'config_cls', None):
            config = test_plugin.load_config()

            assert config is None

    def test_load_config_file_not_found(self, test_plugin, temp_config_dir):
        '''Test loading config when file doesn't exist'''

        @dataclass
        class TestConfig(ConfigBase):
            api_key: str = ''

        with patch.object(test_plugin, 'config_cls', TestConfig):
            with pytest.raises(PluginRequiresConfigError):
                test_plugin.load_config()

    def test_load_config_success(self, test_plugin, temp_config_dir):
        '''Test successfully loading config'''

        @dataclass
        class TestConfig(ConfigBase):
            api_key: str = ''
            timeout: int = 5

        config_file = Path(temp_config_dir) / 'informa.plugins.test_plugin.yaml'
        config_file.write_text('api_key: secret123\ntimeout: 10\n')

        with patch.object(test_plugin, 'config_cls', TestConfig):
            config = test_plugin.load_config()

            assert config.api_key == 'secret123'
            assert config.timeout == 10

    def test_load_config_empty_file(self, test_plugin, temp_config_dir):
        '''Test loading empty config file'''

        @dataclass
        class TestConfig(ConfigBase):
            api_key: str = ''

        config_file = Path(temp_config_dir) / 'informa.plugins.test_plugin.yaml'
        config_file.write_text('')

        with patch.object(test_plugin, 'config_cls', TestConfig):
            config = test_plugin.load_config()

            assert config is None


class TestPluginExecution:
    '''Test plugin execution'''

    def test_execute_simple_plugin(self, test_plugin, temp_state_dir):
        '''Test executing a simple plugin'''
        call_count = 0

        def main_func(state: StateBase) -> int:
            nonlocal call_count
            call_count += 1
            return 5

        with patch.object(test_plugin, 'main_func', main_func):
            with patch.object(test_plugin, 'config_cls', None):
                test_plugin.execute(sync=True)

        assert call_count == 1

        # Check state was updated
        state = test_plugin.load_state()
        assert state.last_count == 5
        assert state.last_run is not None

    def test_execute_plugin_with_config(self, test_plugin, temp_state_dir, temp_config_dir):
        '''Test executing plugin that requires config'''

        @dataclass
        class TestConfig(ConfigBase):
            value: int = 10

        config_file = Path(temp_config_dir) / 'informa.plugins.test_plugin.yaml'
        config_file.write_text('value: 42\n')

        received_config = None

        def main_func(state: StateBase, config: TestConfig) -> int:
            nonlocal received_config
            received_config = config
            return 1

        with patch.object(test_plugin, 'main_func', main_func):
            with patch.object(test_plugin, 'config_cls', TestConfig):
                test_plugin.execute(sync=True)

        assert received_config is not None
        assert received_config.value == 42

    def test_execute_plugin_returns_none(self, test_plugin, temp_state_dir):
        '''Test executing plugin that returns None'''

        def main_func(state: StateBase):
            return None

        with patch.object(test_plugin, 'main_func', main_func):
            with patch.object(test_plugin, 'config_cls', None):
                test_plugin.execute(sync=True)

        # Should default to 1 when None is returned
        state = test_plugin.load_state()
        assert state.last_count == 1

    def test_execute_plugin_handles_app_error(self, test_plugin, temp_state_dir):
        '''Test executing plugin that raises AppError'''

        def main_func(state: StateBase) -> int:
            raise AppError('Test error')

        with patch.object(test_plugin, 'main_func', main_func):
            with patch.object(test_plugin, 'config_cls', None):
                with patch('informa.lib.plugin.raise_alarm') as mock_alarm:
                    test_plugin.execute(sync=True)

                    mock_alarm.assert_called_once()

    def test_execute_plugin_mqtt_publish(self, test_plugin, temp_state_dir):
        '''Test plugin publishes to MQTT when running async'''

        def main_func(state: StateBase) -> int:
            return 3

        # Mock the logger to have a proper level
        test_plugin.logger = Mock()
        test_plugin.logger.getEffectiveLevel.return_value = logging.INFO

        with patch.object(test_plugin, 'main_func', main_func):
            with patch.object(test_plugin, 'config_cls', None):
                with patch('informa.lib.plugin.publish_plugin_run_to_mqtt') as mock_mqtt:
                    test_plugin.execute(sync=False)

                    mock_mqtt.assert_called_once()

    def test_execute_plugin_no_mqtt_when_sync(self, test_plugin, temp_state_dir):
        '''Test plugin doesn't publish to MQTT when running sync'''

        def main_func(state: StateBase) -> int:
            return 3

        with patch.object(test_plugin, 'main_func', main_func):
            with patch.object(test_plugin, 'config_cls', None):
                with patch('informa.lib.plugin.publish_plugin_run_to_mqtt') as mock_mqtt:
                    test_plugin.execute(sync=True)

                    mock_mqtt.assert_not_called()


class TestMqttSetup:
    '''Test MQTT setup'''

    @patch('informa.lib.plugin.mqtt_publish.single')
    def test_setup_mqtt(self, mock_mqtt_publish, test_plugin):
        '''Test MQTT autodiscovery setup'''
        test_plugin.setup_mqtt()

        # Should publish two config messages (last_run and last_count)
        assert mock_mqtt_publish.call_count == 2

        # Check topics
        calls = mock_mqtt_publish.call_args_list
        topics = [call[0][0] for call in calls]
        assert any('last_run' in topic for topic in topics)
        assert any('last_count' in topic for topic in topics)


class TestCachedProperties:
    '''Test cached properties'''

    def test_state_cls_default(self, test_plugin):
        '''Test state_cls returns StateBase by default'''
        assert test_plugin.state_cls == StateBase

    def test_config_cls_default(self, test_plugin):
        '''Test config_cls returns None by default'''
        assert test_plugin.config_cls is None

    def test_logger_property(self, test_plugin):
        '''Test logger property returns PluginAdapter'''
        from informa.lib import PluginAdapter

        assert isinstance(test_plugin.logger, PluginAdapter)
