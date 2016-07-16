from ..plugins.base.httpgrep import HttpGrepPlugin
from ..alerts.zapier import ZapierWebHook

from datetime import timedelta


class PCCaseGearPlugin(HttpGrepPlugin):
    run_every = timedelta(hours=6)

    url = 'http://www.pccasegear.com/index.php?main_page=index&cPath=207_23'
    terms = ['NH-D14', 'NH-D15']


    def process(self):
        data = super().process()

        if 'NH-D15' in data and data['NH-D15'] is True:
            ZapierWebHook.send('ND-15 now available', subject='ND-15')
            self.logger.info('Zapier Webhook called')

        return data
