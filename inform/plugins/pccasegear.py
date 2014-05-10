from ..base_plugins.httpgrep import HttpGrepPlugin
from ..alerts.zapier import ZapierWebHook

from datetime import timedelta


class PCCaseGearPlugin(HttpGrepPlugin):
    run_every = timedelta(hours=6)

    url = 'http://www.pccasegear.com/index.php?main_page=index&cPath=207_23'
    terms = ['NH-D14', 'NH-D15']


    def process(self):
        data = super(PCCaseGearPlugin, self).process()

        if data['NH-D15'] is True:
            alert = ZapierWebHook.prepare()
            alert.send('ND-15 now available', subject='ND-15')
            self.log('Zapier Webhook called')

        return data
