from .base import InformaBasePlugin
from ..alerts.zapier import ZapierWebHook

from datetime import timedelta

import requests

from xml.etree import ElementTree

FEED_RSS = 'https://github.com/mitchellh/vagrant/releases.atom'


class VagrantupPlugin(InformaBasePlugin):
    run_every = timedelta(days=1)
    persist = True

    def process(self):
        try:
            r = requests.get(FEED_RSS)
        except:
            print("Failed loading from {}".format(FEED_RSS))
            return {}

        data = {}

        try:
            # extract Vagrant latest version
            doc = ElementTree.fromstring(r.text)
            nodes = doc.findall('.//{0}entry/{0}title'.format('{http://www.w3.org/2005/Atom}'))
            if len(nodes) == 0:
                raise Exception('No title nodes found in XML')

            data['latest_version'] = nodes[0].text

        except Exception as e:
            print("Error parsing XML: {}".format(e))
            return {}

        # load previous entry
        previous = self.load()

        # raise alert when new Vagrant version released
        if previous is not None and data['latest_version'] != previous['latest_version']:
            ZapierWebHook.send(
                'Goto http://www.vagrantup.com/downloads.html',
                subject='Vagrant {} released'.format(data['latest_version'])
            )
            self.log('Zapier Webhook called')

        return data
