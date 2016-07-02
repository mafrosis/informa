import datetime

from flask import current_app as app
import requests

from ..plugins.base import InformaBasePlugin


class ZapierWebHook:
    @classmethod
    def send(cls, message, subject=None, webhook_url=None):
        if webhook_url is None:
            webhook_url = 'https://zapier.com/hooks/catch/{}/'.format(
                app.config.get('ZAPIER_EMAIL_WEBHOOK_ID', '')
            )

        requests.post(webhook_url, params={
            'message': message,
            'subject': subject if subject else 'Informa Notification',
        })


class ZapierHeartbeatPlugin(InformaBasePlugin):
    run_every = datetime.timedelta(days=1)
    enabled = app.config.get('ZAPIER_EMAIL_HEARTBEAT', False)

    def process(self):
        ZapierWebHook.send(self.load(), subject='Zapier heartbeat')
        return {'heartbeat': datetime.datetime.now().isoformat()}
