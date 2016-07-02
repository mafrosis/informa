import datetime

from flask import current_app as app
import requests

from ..plugins.base.heartbeat import HeartbeatPlugin


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


class ZapierHeartbeatPlugin(HeartbeatPlugin):
    run_every = datetime.timedelta(days=1)
    enabled = app.config.get('ZAPIER_EMAIL_HEARTBEAT', False)

    def process(self):
        # dump all plugin data into an alert via Zapier
        alert_content = super().process()

        ZapierWebHook.send(alert_content, subject='Zapier heartbeat')
        return {'heartbeat': datetime.datetime.now().isoformat()}
