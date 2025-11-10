# Agent Conventions for Informa

This document defines coding conventions and guidelines for AI agents working on the Informa project. These conventions ensure consistency, quality, and maintainability.

## Project Overview

Informa is a Python-based task scheduling and automation framework built on Rocketry. It features:
- Plugin-based architecture for modular functionality
- Scheduled task execution with Rocketry
- FastAPI-based REST API for management
- Click-based CLI interface
- State persistence with JSON
- Configuration via YAML files
- MQTT integration for Home Assistant
- Google Workspace integrations (Gmail, Sheets)

## Python Version and Core Principles

- **Target Python version:** 3.11+ (currently 3.14)
- **Build system:** Hatchling with uv installer
- **Package management:** All dependencies in `pyproject.toml` (never `requirements.txt`)
- **Linting/Formatting:** Ruff with configuration in `ruff.toml`
- **Type checking:** mypy with strict type hints
- **Testing:** pytest with pytest-sugar and pytest-mypy

## Code Quality Standards

### 1. Type Hints
- **Always use type hints** for function parameters and return values
- Use **PEP585** (standard collections) and **PEP604** (union types with `|`) conventions:
  ```python
  # Good
  def process_items(items: list[str] | None = None) -> dict[str, int]:
      pass
  
  # Bad
  from typing import List, Dict, Optional, Union
  def process_items(items: Optional[List[str]] = None) -> Dict[str, Union[str, int]]:
      pass
  ```
- Use `typing.TypeVar` for generic types when needed
- Leverage `from __future__ import annotations` if forward references are required

### 2. String Formatting
- **Use single quotes** for all strings and docstrings (not double quotes)
- **Use f-strings** for string formatting:
  ```python
  # Good
  message = f'Processing {count} items from {source}'
  
  # Bad
  message = 'Processing {} items from {}'.format(count, source)
  message = 'Processing %s items from %s' % (count, source)
  ```
- **Never use f-strings in logging functions**; use idiomatic string formatting:
  ```python
  # Good
  logger.info('Processing %s items from %s', count, source)
  
  # Bad
  logger.info(f'Processing {count} items from {source}')
  ```

### 3. Docstrings
- Use **Google-style docstrings** with single quotes
- Include type information for parameters and returns
- Example:
  ```python
  def extract_wines(item_url: str, order_line: OrderLine | None = None) -> list[Wine]:
      '''
      Extract the wines listed on a TOB product page
  
      Args:
          item_url: Product page URL
          order_line: Optional order line information for pricing
  
      Returns:
          List of Wine objects extracted from the page
  
      Raises:
          NoExtractionError: If wine data cannot be extracted
      '''
  ```

### 4. Function Design
- **Keep functions small:** Each function should do one thing well
- **Single Responsibility Principle:** Functions should have one clear purpose
- Use descriptive function names that indicate what they do
- Limit function parameters (prefer dataclasses for complex parameter groups)

### 5. Data Structures
- Use **list and dict comprehensions** for readability and efficiency:
  ```python
  # Good
  active_plugins = [p for p in plugins if p.enabled]
  
  # Avoid
  active_plugins = []
  for p in plugins:
      if p.enabled:
          active_plugins.append(p)
  ```
- Use **generators for large datasets** to save memory:
  ```python
  def process_messages():
      for msg in get_all_messages():  # Generator
          yield process(msg)
  ```

### 6. Error Handling
- **Implement robust error handling** when calling external dependencies
- **Avoid catching bare `Exception`**; catch only exceptions expected in the try block:
  ```python
  # Good
  try:
      resp = requests.get(url, timeout=5)
      resp.raise_for_status()
  except (requests.RequestException, requests.Timeout) as e:
      logger.error('Failed to fetch URL: %s', e)
  
  # Bad
  try:
      resp = requests.get(url, timeout=5)
  except Exception as e:
      logger.error('Something went wrong: %s', e)
  ```
- Respect the Ruff ignore rules in `ruff.toml` (e.g., TRY003, TRY400, TRY401)

### 7. Logging
- Use the **PluginAdapter** for plugin-specific logging
- **Avoid print statements** unless displaying CLI output to users
- Use appropriate log levels: DEBUG, INFO, WARNING, ERROR
- Never use f-strings in log calls (see String Formatting above)

### 8. Datetime Handling
- **Always pass a timezone** to `datetime.now()`:
  ```python
  from zoneinfo import ZoneInfo
  
  # Good
  now = datetime.now(ZoneInfo('Australia/Melbourne'))
  
  # Bad
  now = datetime.now()
  ```
- Use `arrow` for human-readable datetime formatting
- Use `pytz` for timezone handling when needed

### 9. Whitespace
- **Never change unrelated whitespace**
- Respect existing indentation style (spaces vs tabs)
- Follow PEP 8 for new code

## Informa-Specific Conventions

### Plugin Development

1. **Plugin Structure:**
   ```python
   import logging
   from dataclasses import dataclass, field
   from informa import app
   from informa.lib import StateBase, ConfigBase, PluginAdapter
   from informa.lib.plugin import InformaPlugin
   
   logger = PluginAdapter(logging.getLogger('informa'))
   
   @dataclass
   class Config(ConfigBase):
       # Plugin configuration fields
       pass
   
   @dataclass
   class State(StateBase):
       # Plugin state fields beyond last_run/last_count
       pass
   
   @app.task('every 12 hours')
   def run(plugin):
       plugin.execute()
   
   def main(state: State, config: Config) -> int:
       # Plugin logic here
       return item_count  # Always return a count
   ```

2. **Plugin main() function:**
   - Must accept `state: State` as first parameter
   - Optionally accepts `config: Config` as second parameter
   - Must return an integer count (number of items processed)
   - Never return `None` (use `0` or `1` as appropriate)

3. **State Management:**
   - Inherit from `StateBase` which provides `last_run` and `last_count`
   - Add plugin-specific state fields as needed
   - State is automatically persisted to JSON after execution
   - State directory: `./state` (or `STATE_DIR` env var)

4. **Configuration:**
   - Inherit from `ConfigBase` using dataclasses-json
   - Config files are YAML in `./config/{plugin_name}.yaml`
   - Config directory: `./config` (or `CONFIG_DIR` env var)

5. **CLI Commands:**
   - Use Click library with decorators
   - Create a Click group named after the plugin
   - First parameter should be `plugin: InformaPlugin` for CLI commands
   - Common commands (`last-run`, `run`) are added automatically

6. **Task Scheduling:**
   - Use `@app.task()` decorator with Rocketry condition strings
   - Examples: `'every 12 hours'`, `'daily at 09:00'`, `'every 5 mins'`

7. **API Routes:**
   - Use `@app.api()` decorator with FastAPI `APIRouter`
   - Router prefix should match plugin name

### Error Handling in Plugins

- Use `raise_alarm()` for critical errors that need attention
- Handle expected exceptions gracefully with appropriate logging
- The plugin execution wrapper catches:
  - `AppError` (application-specific errors)
  - `ValidationError` (dataclass validation)
  - Generic exceptions (logged as unhandled)

### Dependencies

- Add to `pyproject.toml` under `[project.dependencies]`
- Pin major versions with `~=` or specific versions with `==`
- For Git dependencies, use: `package @ git+https://github.com/user/repo.git`
- Test dependencies go in `[tool.hatch.envs.test]`

### Testing

- Place tests in `test/` directory
- Use pytest with fixtures in `conftest.py`
- Fixtures for test data in `test/fixtures/`
- Run tests: `make test` or `hatch run test:test`
- Run type checking: `make typecheck` or `hatch run test:mypy`

### Code Style

- Format code: `make lint` or `hatch fmt --preview`
- Respect `ruff.toml` configuration:
  - Line length: 120 characters
  - Quote style: preserve (use single quotes)
  - Ignore rules are explicitly defined (see ruff.toml)

## Design Patterns

### 1. Dataclasses
- Use `@dataclass` for data structures
- Use `field(default_factory=list)` for mutable defaults
- Leverage `dataclasses-json` for (de)serialization

### 2. Object-Oriented Design
- Use inheritance where appropriate (StateBase, ConfigBase)
- Favor composition over inheritance for complex behaviors
- Use abstract base classes (`abc.ABC`) for interfaces

### 3. Async/Await
- Main application uses asyncio for concurrent task execution
- Plugin `main()` functions are synchronous (called from async context)
- Use `async`/`await` only when necessary for I/O-bound operations

### 4. Dependency Injection
- Plugins receive their configuration and state as parameters
- Use context passing for CLI commands (`@click.pass_obj`)
- FastAPI handles dependency injection for API routes

## External Integrations

### Google Workspace
- Use service account credentials from `GSUITE_OAUTH_CREDS` env var
- Use `gmsa` library for Gmail operations
- Use `gspread` for Google Sheets operations

### MQTT/Home Assistant
- Publish plugin state to MQTT topics
- Use autodiscovery for HA sensor configuration
- Default broker: `trevor:1883`

### Web Scraping
- Use `requests` with proper timeouts (default: 5 seconds)
- Use `beautifulsoup4` for HTML parsing
- Use `playwright` for JavaScript-rendered pages
- Include User-Agent headers with `fake-useragent`

## Common Gotchas

1. **Module names:** Convert dashes to underscores in plugin file names
2. **Plugin naming:** Full plugin names are `informa.plugins.{name}`
3. **State persistence:** State is only saved after successful execution
4. **Config reload:** Configuration is reloaded on every plugin execution
5. **Working directory:** Plugins run with `state_dir` as current working directory
6. **Return values:** Always return an integer from `main()`, never None

## Commands Reference

```bash
# Start Informa server
informa start --host 127.0.0.1 --port 3000

# Start with specific plugins
informa start --plugins tob,kindle_gcal

# List plugins
informa admin list

# Enable/disable plugins
informa admin enable plugin_name --persist
informa admin disable plugin_name --persist

# Run plugin CLI commands
informa plugin {plugin_name} {command}
informa plugin {plugin_name} last-run
informa plugin {plugin_name} run

# Development
make lint      # Format code with ruff
make typecheck # Run mypy type checking
make test      # Run pytest
make dist      # Build distribution
```

## Resources

- Rocketry: https://rocketry.readthedocs.io/
- FastAPI: https://fastapi.tiangolo.com/
- Click: https://click.palletsprojects.com/
- Ruff: https://docs.astral.sh/ruff/
