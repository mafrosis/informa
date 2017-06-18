import datetime

import requests

from .base import InformaBasePlugin
from .base.alerts.zapier import ZapierWebHook


UKFOREX_GBP_AUD = 'http://www.ukforex.co.uk/forex-tools/chart-data/GBP/AUD/168/day/true'
OFX_GBP_AUD = 'https://api.ofx.com/PublicSite.ApiService/SpotRateHistory/day/GBP/AUD?format=json'
ALERT_THRESHOLD = 1.8

EMAIL_TEMPLATE = 'Exchange rate hit {rate} on {date}\n\nPrevious week trend:\n\n{trend}'


class UKForexPlugin(InformaBasePlugin):
    run_every = datetime.timedelta(minutes=1)

    def process(self):
        resp = requests.get(OFX_GBP_AUD)
        if resp.status_code != 200:
            self.logger.error('Bad response from ofx.com: {}'.format(resp.status_code))

        data = resp.json()

        self.logger.debug('Request finished')

        # always send daily alert at 7am
        if datetime.datetime.now().hour == 7:
            global ALERT_THRESHOLD
            ALERT_THRESHOLD = 1

        # alert when exchange rate over threshold
        if data['CurrentInterbankRate'] > ALERT_THRESHOLD:
            email_data = self.format_for_email(data['CurrentInterbankRate'])
            ZapierWebHook.send(
                EMAIL_TEMPLATE.format(**email_data),
                subject=email_data['subject']
            )

            ## invert numbers for Gina
            #email_data = self.format_for_email(data['CurrentInverseInterbankRate'])
            #ZapierWebHook.send(
            #    EMAIL_TEMPLATE.format(**email_data),
            #    subject=email_data['subject'],
            #    webhook_url='https://hooks.zapier.com/hooks/catch/74441/4ta8iy/'
            #)
            #self.logger.info('Zapier Webhook called')

        return data

    def format_for_email(self, rate):
        # format data for email
        return {
            'subject': 'AUD at {} to GBP'.format('{:.3f}'.format(rate)),
            'rate': rate,
            'date': datetime.datetime.now().strftime("%A %d %B %Y"),
        }
