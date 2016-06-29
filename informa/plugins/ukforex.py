import datetime

import requests

from .base import InformaBasePlugin
from ..alerts.zapier import ZapierWebHook


UKFOREX_GBP_AUD = 'http://www.ukforex.co.uk/forex-tools/chart-data/GBP/AUD/168/day/true'
ALERT_THRESHOLD = 1.5


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
            alert = ZapierWebHook.prepare()
            alert.send(
                'Exchange rate hit {} on {}\n\nPrevious week trend:\n\n{}'.format(
                    data[0][1],
                    datetime.datetime.strptime(data[0][0], "%Y-%m-%dT%H:%M:%S").strftime("%A %d %B %Y"),
                    '\n'.join(['{:.3f}'.format(d[1]) for d in data[1:8]]),
                ),
                subject='AUD at {} to GBP'.format('{:.3f}'.format(data[0][1]))
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

        self.store(data)
        return data
