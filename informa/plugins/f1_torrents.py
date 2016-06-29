import datetime
import os
from urllib.parse import urlparse

from xml.etree import ElementTree

import requests

from .base import InformaBasePlugin


TORRENT_RSS = 'https://kat.cr/usearch/user%3Asmcgill1969/?rss=1'
WATCH_DIR = '/var/app/watch'


class F1Plugin(InformaBasePlugin):
    run_every = datetime.timedelta(hours=6)
    persist = True

    def process(self):
        try:
            resp = requests.get(TORRENT_RSS, timeout=5)
        except:
            self.log('Failed loading from {}'.format(TORRENT_RSS))
            return {}

        # load previous run data
        data = self.load()
        if not data:
            data = {
                'latest_race': 0,
                'races': {}
            }

        try:
            # extract items from PB feed
            doc = ElementTree.fromstring(resp.text)
            nodes = doc.findall('.//channel/item')
            if len(nodes) == 0:
                raise Exception('No item nodes found in XML')

            # find the F1 torrents
            for item in nodes:
                title = item.find('title').text
                if 'Formula 1' in title and '720p50' in title:
                    race_number = int(title[15:17])

                    # track the current race number
                    if race_number > data.get('latest_race', 0):
                        data['latest_race'] = race_number

                    # find torrents for current race
                    race_id = '{}x{:02d}'.format(datetime.date.today().year, race_number)

                    if race_id in title:
                        if race_id not in data['races']:
                            data['races'][race_id] = {}

                        # iterate parts of race
                        for part in ('Race Pt 02-RACE', 'Race Pt 01-BUILDUP', 'Qualifying Pt 02-QUALIFYING'):
                            if part in title:
                                if part not in data['races'][race_id]:
                                    data['races'][race_id][part] = {
                                        'title': item.find('title').text,
                                        'url': item.find('guid').text,
                                        'magnet': item.find('{/content/xmlns/0.1/}magnetURI').text,
                                        'done': False,
                                    }


        except Exception as e:
            self.log('Error parsing XML: {}'.format(e))
            return {}

        for race_id, race_data in data['races'].items():
            for part, part_data in race_data.items():
                if part_data['done'] is False:
                    # parse magnet link to create torrent filename
                    qs = urlparse(part_data['magnet']).query.split('&')
                    filename = next((p[3:] for p in qs if p.startswith('dn=')), '')
                    hash_ = qs[0][12:]

                    # convert magnet links to torrent file via API
                    resp = requests.post(
                        'http://magnet2torrent.com/upload/',
                        headers={
                            'User-Agent': 'Mozilla/5.0'
                        },
                        data={
                            'magnet': part_data['magnet']
                        }
                    )

                    # write torrent into watch dir
                    with open(os.path.join(WATCH_DIR, 'magnet-{}-{}.torrent'.format(filename, hash_)), 'wb') as f:
                        f.write(resp.content)

                    # TODO proper logger for all plugins
                    self.log('Created torrent for {}'.format(filename))
                    part_data['done'] = True

        self.store(data)
        return data
