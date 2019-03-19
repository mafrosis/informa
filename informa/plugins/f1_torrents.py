#import datetime
import os
import datetime
import time
from urllib.parse import urlparse

import bs4

from celery.schedules import crontab
import requests

from .base import InformaBasePlugin
from ..lib.rtorrent import RTorrent, RtorrentError


RTORRENT_HOST = 'jorg'
TORRENT_URL = 'https://katcr.co/get/user-uploads/62512875/authtoken/37217f748d3b661c8587e5de3f7caa541/'
#TORRENT_URLS = {
#    'kat': 'https://katcr.co/user/smcgill1969/uploads/page/',
#    'pb': 'https://thepiratebay.org/user/smcgill1969/',
#}


class F1Plugin(InformaBasePlugin):
    run_every = crontab(minute='*/1')

    def process(self, data):
        '''
        Three parts:
            - Check for new F1 torrents
            - Process magnet URIs into torrent files
            - Set priorty on qualy/race files within torrent
            - Check download status and move
        '''
        if not data:
            data = {
                'latest_race': 0,
                'races': {}
            }

        # plugin runs every minute; only check for torrents every 15 mins
        if self.force is True or datetime.datetime.now().minute % 15 == 0:
            self._check_for_new(data)

        # add magnets to rtorrent
        self._add_magnet_to_rtorrent(data)

        try:
            self._set_torrent_file_priorities(data)
        except RtorrentError as e:
            self.logger.error(e)

        # TODO now I can set tags, what about move-torrent??
        #self._check_complete()

        return data


    def _set_torrent_file_priorities(self, data):
        rt = RTorrent(RTORRENT_HOST, 5000)
        torrents = rt.get_torrents()

        for hash_id, torrent_data in torrents.items():
            if 'Formula.1.' in torrent_data['name']:
                # set label on F1 torrents
                rt.set_tag(hash_id, 'F1')

                # load torrent files and their index
                for i, file_data in enumerate(torrent_data['files']):
                    # disable first and last parts for qualy
                    if 'Pre-Race.Buildup' not in file_data['filename'] and 'Session' not in file_data['filename']:
                        rt.set_file_priority(hash_id, i, 0)
                        self.logger.info('Disabled {} on {}'.format(
                            file_data['filename'],
                            torrent_data['name'],
                        ))


    #@retry(times=3, sleep=3)
    def _check_for_new(self, data):
        try:
            resp = requests.get(TORRENT_URL, timeout=5)
        except:
            self.logger.error('Failed loading from {}'.format(TORRENT_URL))
            # retry with pb if kat is down
            #if host == 'kat':
            #    return self.process('pb')
            return

        # find the latest F1 race
        for item in resp.json():
            title = item['torrent_name']

            if 'Formula 1' in title and 'SkyF1HD 1080p50' in title:
                race_number = int(title[15:17])

                # store for next time
                if race_number > data.get('latest_race', 0):
                    data['latest_race'] = race_number

        # find torrents for latest race
        race_id = '2018x{:02d}'.format(data['latest_race'])
        self.logger.debug('Found race {}'.format(race_id))

        for item in resp.json():
            title = item['torrent_name'].replace(' ', '.')

            if title.startswith('Formula.1.{}'.format(race_id)) and title.endswith('SkyF1HD.1080p50'):
                if not 'Race' in title and not 'Qualifying' in title:
                    continue
                if 'Teds' in title:
                    continue

                try:
                    ok = False
                    trys = 0

                    sess = requests.Session()
                    url = 'https://katcr.co/torrent/{}/{}.html'.format(
                        item['hashed_id'], item['page_link']
                    )
                    self.logger.debug('Loading {}'.format(url))

                    while ok is False and trys <= 2:
                        sess.head(url, timeout=5)
                        resp = sess.get(url, timeout=5)

                        if 'ERROR LOADING CONTENT' in resp.text:
                            trys += 1
                            time.sleep(1)
                            self.logger.debug('Retry {}'.format(trys))
                        else:
                            ok = True

                    if trys >= 2:
                        self.logger.error('Failed loading KAT torrent page: {}'.format(url))
                        continue

                    soup = bs4.BeautifulSoup(resp.text, 'html.parser')

                    magnet = next(iter([
                        a.attrs['href']
                        for a in soup.select('a.button--special_icon')
                        if a.attrs['href'].startswith('magnet')
                    ]), None)

                    self.logger.debug('Got magnet {}'.format(magnet))

                    if not magnet:
                        self.logger.error('Failed getting magnet on {}'.format(url))
                        continue

                    if race_id not in data['races']:
                        data['races'][race_id] = dict()

                    event = 'r' if 'Race' in title else 'q'

                    if event not in data['races'][race_id]:
                        data['races'][race_id][event] = {
                            'title': title,
                            'url': url,
                            'magnet': magnet,
                            'added_to_rtorrent': False,
                        }
                except:
                    self.logger.error('Failed loading from {}'.format(item['page_link']))


    def _add_magnet_to_rtorrent(self, data):
        '''
        Add magnets directly to rtorrent via RPC
        '''
        for race_id, stages in data['races'].items():
            for stage, race_data in stages.items():

                if race_data['added_to_rtorrent'] is False:
                    rt = RTorrent(RTORRENT_HOST, 5000)
                    rt.add_magnet(race_data['magnet'])

                    # parse magnet link to get torrent filename
                    qs = urlparse(race_data['magnet']).query.split('&')
                    filename = next((p[3:] for p in qs if p.startswith('dn=')), '')

                    self.logger.info('MAGNET torrent for {}'.format(filename))
                    race_data['added_to_rtorrent'] = True
