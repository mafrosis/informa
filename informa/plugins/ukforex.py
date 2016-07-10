import datetime

import requests

from .base import InformaBasePlugin
from ..alerts.zapier import ZapierWebHook


UKFOREX_GBP_AUD = 'http://www.ukforex.co.uk/forex-tools/chart-data/GBP/AUD/168/day/true'
ALERT_THRESHOLD = 1.5

EMAIL_TEMPLATE = 'Exchange rate hit {rate} on {date}\n\nPrevious week trend:\n\n{trend}'


class UKForexPlugin(InformaBasePlugin):
    run_every = datetime.timedelta(hours=4)

    def process(self):
        resp = requests.get(UKFOREX_GBP_AUD)
        raw_data = resp.json()

        # create list of tuples, converting timestamps to datetime (removing trailing zeros)
        data = [
            (datetime.datetime.utcfromtimestamp(int(str(p[0])[0:10])).isoformat(), p[1],)
            for p in reversed(raw_data)
        ][0:10]

        # alert when exchange rate over threshold
        if data[0][1] > ALERT_THRESHOLD:
            email_data = self.format_for_email(data)
            ZapierWebHook.send(
                EMAIL_TEMPLATE.format(**email_data),
                subject=email_data['subject']
            )

            # invert numbers for Gina
            data = [
                (datetime.datetime.utcfromtimestamp(int(str(p[0])[0:10])).isoformat(), 1/p[1],)
                for p in reversed(raw_data)
            ][0:10]
            email_data = self.format_for_email(data)
            ZapierWebHook.send(
                EMAIL_TEMPLATE.format(**email_data),
                subject=email_data['subject'],
                webhook_url='https://hooks.zapier.com/hooks/catch/74441/4ta8iy/'
            )
            self.log('Zapier Webhook called')

        return data

    def format_for_email(self, data):
        # format data for email
        return {
            'subject': 'AUD at {} to GBP'.format('{:.3f}'.format(data[0][1])),
            'rate': data[0][1],
            'date': datetime.datetime.strptime(data[0][0], "%Y-%m-%dT%H:%M:%S").strftime("%A %d %B %Y"),
            'trend': '\n'.join(['{:.3f}'.format(d[1]) for d in data[1:8]]),
        }
