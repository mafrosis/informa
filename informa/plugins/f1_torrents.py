from ..base_plugins import InformaBasePlugin
from ..alerts.zapier import ZapierWebHook

from datetime import timedelta

import requests

from xml.etree import ElementTree


TORRENT_RSS = "http://rss.thepiratebay.se/user/73e91b52f5f52aecb389b8f233aa1323"


class F1Plugin(InformaBasePlugin):
    run_every = timedelta(hours=6)

    def process(self):
        try:
            r = requests.get(TORRENT_RSS)
        except:
            print "Failed loading from {}".format(TORRENT_RSS)
            return {}

        data = {}

        try:
            # extract items from PB feed
            doc = ElementTree.fromstring(r.text)
            nodes = doc.findall('.//channel/item')
            if len(nodes) == 0:
                raise Exception('No title nodes found in XML')

            # find the F1 torrents
            for n in nodes:
                title = n.find('title').text
                if 'Formula.1' in title and '720p' in title:
                    # break on the first 720p F1 entry
                    data['latest_race'] = n.find('title').text
                    data['url'] = n.find('guid').text
                    break

        except Exception as e:
            print "Error parsing XML: {}".format(e)
            return {}

        # load previous entry
        previous = self.load(persistent=True)

        # raise alert when race differs from previous
        if previous is not None and data['latest_race'] != previous['latest_race']:
            alert = ZapierWebHook.prepare()
            alert.send(
                '{0} released at:\n\n{1}', subject='{0} released'.format(
                    data['latest_race'], data['magnet_url'],
                )
            )
            self.log('Zapier Webhook called')

        # store in memcache and persist for next run
        self.store(data, persistent=True)
        return data
