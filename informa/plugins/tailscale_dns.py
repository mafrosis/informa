import logging
import os
from dataclasses import dataclass, field

import click
import requests

from informa import app
from informa.lib import PluginAdapter, StateBase
from informa.lib.plugin import load_run_persist, load_state
from informa.lib.utils import raise_alarm

logger = PluginAdapter(logging.getLogger('informa'))


@dataclass
class Device:
    hostname: str
    ip: str


@dataclass
class State(StateBase):
    tailnet: dict[str, str] = field(default_factory=dict)


@app.task('every 10 minutes')
def run():
    'Run the scheduled task to update DNS records'
    load_run_persist(logger, State, main)


def main(state: State) -> int:
    'Main processing logic to update DNS records for Linux machines'
    devices = fetch_tailscale_devices()
    if not devices:
        return 0

    updated = 0
    for device in devices:
        # If current IP differs from informa state, update Gandi DNS and refresh state
        if state.tailnet.get(device.hostname) != device.ip and update_dns_record(device.hostname, device.ip):
            state.tailnet[device.hostname] = device.ip
            updated += 1
            logger.info('Updated %s.mafro.net -> %s', device.hostname, device.ip)

    return updated


def fetch_tailscale_devices() -> list[Device] | None:
    'Fetch devices from Tailscale API'
    tailscale_api_key = os.getenv('TAILSCALE_API_KEY')
    if not tailscale_api_key:
        logger.error('TAILSCALE_API_KEY environment variable is not set')
        return None

    try:
        resp = requests.get(
            'https://api.tailscale.com/api/v2/tailnet/mafro.net/devices',
            headers={'Authorization': f'Bearer {tailscale_api_key}'},
            timeout=10,
        )
        resp.raise_for_status()

        # Return linux tailnet hosts as Device objects with an ipv4 address
        return [
            Device(device['hostname'], next(ip for ip in device['addresses'] if ':' not in ip))
            for device in resp.json().get('devices', [])
            if device.get('os', '') == 'linux'
        ]

    except requests.RequestException as e:
        logger.error('Failed to fetch Tailscale devices: %s', e)
        return None
    except (KeyError, StopIteration):
        raise_alarm(logger, 'Tailscale device data format changed!')
        return None


def update_dns_record(hostname: str, ip: str) -> bool:
    'Update DNS record via Gandi API'
    gandi_api_key = os.getenv('GANDI_API_KEY')
    if not gandi_api_key:
        logger.error('GANDI_API_KEY environment variable is not set')
        return False

    try:
        # PUT overwrites an existing hostname/type record
        resp = requests.put(
            f'https://api.gandi.net/v5/livedns/domains/mafro.net/records/{hostname}/A',
            headers={'Authorization': f'Bearer {gandi_api_key}'},
            json={'rrset_values': [ip], 'rrset_ttl': 300},
            timeout=10,
        )
        resp.raise_for_status()

    except requests.RequestException as e:
        logger.error('Gandi API failed for %s: %s', hostname, e)
        return False
    else:
        return True


@click.group(name='tailscale-dns')
def cli():
    'Tailscale DNS manager'


@cli.command
def current():
    'Show current DNS mappings'
    state = load_state(logger, State)
    for hostname, ip in state.last_ips.items():
        click.echo(f'{hostname}.mafro.net: {ip}')
