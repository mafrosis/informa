import datetime

from .. import app
from ..plugins.base.heartbeat import HeartbeatPlugin

import requests


EMAIL_WEBHOOK_URL = 'https://zapier.com/hooks/catch/{}/'.format(
    app.config.get('ZAPIER_EMAIL_WEBHOOK_ID', '')
)


class ZapierWebHook:
    @staticmethod
    def prepare(webhook_url=None):
        alert = ZapierWebHook()
        if webhook_url is not None:
            alert.url = webhook_url
        else:
            alert.url = EMAIL_WEBHOOK_URL
        return alert

    def send(self, message, subject=None):
        params = {'message': message}
        if subject is not None:
            params['subject'] = subject

        requests.post(self.url, params=params)


class ZapierHeartbeatPlugin(HeartbeatPlugin):
    run_every = datetime.timedelta(days=1)
    enabled = app.config.get('ZAPIER_EMAIL_HEARTBEAT', False)

    def process(self):
        # dump all plugin data into an alert via Zapier
        alert_content = super().process()

        alert = ZapierWebHook.prepare()
        alert.send(alert_content, subject='Zapier heartbeat')
        return {'heartbeat': datetime.datetime.now().isoformat()}
