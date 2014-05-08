from __future__ import absolute_import

from .. import app

import requests

EMAIL_WEBHOOK_URL = 'https://zapier.com/hooks/catch/{}/'.format(
    app.config['ZAPIER_EMAIL_WEBHOOK_ID']
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
