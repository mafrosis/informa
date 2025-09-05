from fastapi import APIRouter

from informa import app

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
async def plugin_enable(plugin_name: str):
    'Enable a plugin'
    app.enable_plugin(plugin_name)
    # app.plugins[plugin_name].enable_plugin = True


@router.delete('/plugins/{plugin_name}')
async def plugin_disable(plugin_name: str):
    'Disable a plugin'
    app.disable_plugin(plugin_name)
    # app.plugins[plugin_name].is_enabled = False
