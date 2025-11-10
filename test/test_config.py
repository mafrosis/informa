import os
import tempfile
from pathlib import Path

import pytest
import yaml

from informa.lib.config import AppConfig, load_app_config, save_app_config


@pytest.fixture
def temp_config_home():
    '''Create a temporary config home directory'''
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
            yield tmpdir


class TestAppConfig:
    '''Test AppConfig dataclass'''

    def test_app_config_default(self):
        '''Test AppConfig with default values'''
        config = AppConfig()

        assert config.disabled_plugins == set()

    def test_app_config_with_plugins(self):
        '''Test AppConfig with disabled plugins'''
        config = AppConfig(disabled_plugins={'plugin1', 'plugin2'})

        assert len(config.disabled_plugins) == 2
        assert 'plugin1' in config.disabled_plugins
        assert 'plugin2' in config.disabled_plugins

    def test_app_config_serialization(self):
        '''Test AppConfig serialization to dict'''
        config = AppConfig(disabled_plugins={'plugin1', 'plugin2'})

        data = config.to_dict()

        assert 'disabled_plugins' in data
        assert isinstance(data['disabled_plugins'], (list, set))

    def test_app_config_deserialization(self):
        '''Test AppConfig deserialization from dict'''
        data = {'disabled_plugins': ['plugin1', 'plugin2']}

        config = AppConfig.from_dict(data)

        assert len(config.disabled_plugins) == 2


class TestLoadAppConfig:
    '''Test loading application config'''

    def test_load_config_creates_directory(self):
        '''Test load_config creates config directory if it doesn't exist'''
        with tempfile.TemporaryDirectory() as tmpdir:
            config_home = Path(tmpdir) / 'config'

            with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(config_home)}):
                config = load_app_config()

                assert (config_home / 'informa').exists()
                assert isinstance(config, AppConfig)

    def test_load_config_no_file(self):
        '''Test loading config when file doesn't exist returns default'''
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
                config = load_app_config()

                assert isinstance(config, AppConfig)
                assert config.disabled_plugins == set()

    def test_load_config_empty_file(self):
        '''Test loading config from empty file returns default'''
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / 'informa'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            config_file.write_text('')

            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
                config = load_app_config()

                assert isinstance(config, AppConfig)
                assert config.disabled_plugins == set()

    def test_load_config_with_data(self):
        '''Test loading config from file with data'''
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / 'informa'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'

            data = {'disabled_plugins': ['plugin1', 'plugin2']}
            config_file.write_text(yaml.dump(data))

            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
                config = load_app_config()

                assert len(config.disabled_plugins) == 2
                assert 'plugin1' in config.disabled_plugins

    def test_load_config_uses_home_default(self):
        '''Test load_config uses ~/.config by default'''
        # Remove XDG_CONFIG_HOME if it exists
        env = os.environ.copy()
        if 'XDG_CONFIG_HOME' in env:
            del env['XDG_CONFIG_HOME']

        with patch.dict(os.environ, env, clear=True):
            with patch('pathlib.Path.home', return_value=Path('/tmp/test_home')):
                from informa.lib.config import _get_app_config_path

                path = _get_app_config_path()

                assert '/tmp/test_home/.config/informa' in str(path)


class TestSaveAppConfig:
    '''Test saving application config'''

    def test_save_config_creates_file(self):
        '''Test save_config creates config file'''
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
                config = AppConfig(disabled_plugins={'plugin1'})

                save_app_config(config)

                config_file = Path(tmpdir) / 'informa' / 'config.yaml'
                assert config_file.exists()

    def test_save_config_writes_data(self):
        '''Test save_config writes correct data'''
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
                config = AppConfig(disabled_plugins={'plugin1', 'plugin2'})

                save_app_config(config)

                config_file = Path(tmpdir) / 'informa' / 'config.yaml'
                with open(config_file, encoding='utf8') as f:
                    data = yaml.safe_load(f)

                assert 'disabled_plugins' in data
                assert len(data['disabled_plugins']) == 2

    def test_save_then_load_roundtrip(self):
        '''Test save and load config roundtrip'''
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
                original = AppConfig(disabled_plugins={'plugin1', 'plugin2', 'plugin3'})

                save_app_config(original)
                loaded = load_app_config()

                assert loaded.disabled_plugins == original.disabled_plugins

    def test_save_config_overwrites_existing(self):
        '''Test save_config overwrites existing config'''
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmpdir}):
                config1 = AppConfig(disabled_plugins={'plugin1'})
                save_app_config(config1)

                config2 = AppConfig(disabled_plugins={'plugin2', 'plugin3'})
                save_app_config(config2)

                loaded = load_app_config()

                assert len(loaded.disabled_plugins) == 2
                assert 'plugin1' not in loaded.disabled_plugins
                assert 'plugin2' in loaded.disabled_plugins


# Import patch here to avoid import errors
from unittest.mock import patch
