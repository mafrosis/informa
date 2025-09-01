from fastapi import APIRouter, HTTPException

from informa import app
from informa.exceptions import PluginAlreadyDisabled, PluginAlreadyEnabled

router = APIRouter(prefix='/admin')


@router.get('/plugins')
def plugin_list():
    'List all registered plugins'
    data = []

    for plugin_name, plugin in sorted(app.plugins.items()):
        tasks = [
            f'{task.func.__name__}, {task.condition}'
            if isinstance(task.condition, str)
            else f'{task.func.__name__}, <condition>'
            for task in plugin.tasks
        ]

        data.append({
            'name': plugin_name,
            'last_run': plugin.last_run,
            'last_count': plugin.last_count,
            'enabled': plugin.enabled,
            'tasks': tasks,
        })

    return data


@router.post('/plugins/{plugin_name}')
def plugin_enable(plugin_name: str, persist: bool = False):
    'Enable a plugin'
    try:
        app.enable_plugin(plugin_name, persist)
    except PluginAlreadyEnabled as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete('/plugins/{plugin_name}')
def plugin_disable(plugin_name: str, persist: bool = False):
    'Disable a plugin'
    try:
        app.disable_plugin(plugin_name, persist)
    except PluginAlreadyDisabled as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
