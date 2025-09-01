import os
import pathlib
from dataclasses import dataclass, field

import yaml
from dataclasses_json import DataClassJsonMixin


@dataclass
class AppConfig(DataClassJsonMixin):
    disabled_plugins: set[str] = field(default_factory=set)


def _get_app_config_path() -> pathlib.Path:
    'Returns the path to the application config file'
    config_dir = os.environ.get('XDG_CONFIG_HOME', f'{pathlib.Path.home()}/.config')
    app_config_dir = pathlib.Path(f'{config_dir}/informa')
    app_config_dir.mkdir(parents=True, exist_ok=True)
    return app_config_dir / 'config.yaml'


def load_app_config() -> AppConfig:
    'Loads the application config'
    config_path = _get_app_config_path()
    if not config_path.exists():
        return AppConfig()

    try:
        with open(config_path, encoding='utf8') as f:
            data = yaml.safe_load(f)
            if not data:
                return AppConfig()
            return AppConfig.from_dict(data)
    except FileNotFoundError:
        return AppConfig()


def save_app_config(config: AppConfig):
    'Saves the application config'
    config_path = _get_app_config_path()
    with open(config_path, 'w', encoding='utf8') as f:
        f.write(yaml.dump(config.to_dict()))
