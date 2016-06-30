import datetime

from .. import app
from ..plugins.base.heartbeat import HeartbeatPlugin

import requests


EMAIL_WEBHOOK_URL = 'https://zapier.com/hooks/catch/{}/'.format(
    app.config.get('ZAPIER_EMAIL_WEBHOOK_ID', '')
)


class ZapierWebHook:
    @classmethod
    def send(cls, message, subject=None, webhook_url=None):
        if webhook_url is None:
            webhook_url = EMAIL_WEBHOOK_URL

        requests.post(webhook_url, params={
            'message': message,
            'subject': subject if subject else 'Informa Notification',
        })


class ZapierHeartbeatPlugin(HeartbeatPlugin):
    run_every = datetime.timedelta(days=1)
    enabled = app.config.get('ZAPIER_EMAIL_HEARTBEAT', False)

    def process(self):
        # dump all plugin data into an alert via Zapier
        alert_content = super().process()

        ZapierWebHook.send(alert_content, subject='Zapier heartbeat')
        return {'heartbeat': datetime.datetime.now().isoformat()}
