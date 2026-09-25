import logging
import os
from dataclasses import dataclass
from typing import cast

import click
import requests

from informa import app
from informa.lib import PluginAdapter, StateBase
from informa.lib.plugin import InformaPlugin

logger = PluginAdapter(logging.getLogger('informa'))

DOMAIN = 'mafro.net'
RECORD = 'ca'
IPIFY_URL = 'https://api.ipify.org?format=json'


@dataclass
class State(StateBase):
    ip: str | None = None


@app.task('every 30 minutes')
def run(plugin):
    plugin.execute()


def main(state: State) -> int:
    'Fetch the current external IP and update the ca.mafro.net DNS record if it changed'
    external_ip = fetch_external_ip()
    if not external_ip:
        return 0

    if state.ip == external_ip:
        logger.debug('External IP unchanged: %s', external_ip)
        return 0

    if not update_dns_record(external_ip):
        return 0

    logger.info('Updated ca.%s -> %s', DOMAIN, external_ip)
    state.ip = external_ip
    return 1


def fetch_external_ip() -> str | None:
    'Fetch the current external IP address from ipify'
    try:
        resp = requests.get(IPIFY_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()['ip']

    except requests.RequestException as e:
        logger.error('Failed to fetch external IP: %s', e)
    except (KeyError, ValueError):
        logger.error('Unexpected ipify response format')
    return None


def update_dns_record(ip: str) -> bool:
    'Update the ca.mafro.net A record via the Gandi API'
    gandi_api_key = os.getenv('GANDI_API_KEY')
    if not gandi_api_key:
        logger.error('GANDI_API_KEY environment variable is not set')
        return False

    try:
        # PUT overwrites an existing hostname/type record
        resp = requests.put(
            f'https://api.gandi.net/v5/livedns/domains/{DOMAIN}/records/{RECORD}/A',
            headers={'Authorization': f'Bearer {gandi_api_key}'},
            json={'rrset_values': [ip], 'rrset_ttl': 300},
            timeout=10,
        )
        resp.raise_for_status()

    except requests.RequestException as e:
        logger.error('Gandi API failed for %s.%s: %s', RECORD, DOMAIN, e)
        return False
    else:
        return True


@click.group(name='external-ip')
def cli():
    'External IP DNS updater'


@cli.command
def current(plugin: InformaPlugin):
    'Show the last known external IP'
    state = cast('State', plugin.load_state())
    click.echo(f'ca.{DOMAIN}: {state.ip or "never set"}')
