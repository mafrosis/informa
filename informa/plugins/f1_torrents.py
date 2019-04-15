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
TORRENT_URL = 'https://katcr.co/user/smcgill1969/uploads/page/'
CURRENT_SEASON = 2019


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

        # prune data history
        data['races'] = {
            k:v for k,v in data['races'].items()
            if k == '{}x{:02d}'.format(CURRENT_SEASON, data['latest_race'])
            or k == '{}x{:02d}'.format(CURRENT_SEASON, data['latest_race']-1)
        }

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
            ok = False
            trys = 0

            sess = requests.Session()
            resp = sess.get(TORRENT_URL, timeout=5)
            self.logger.debug('Loading {}'.format(TORRENT_URL))

            while ok is False and trys <= 2:
                sess.head(TORRENT_URL, timeout=5)
                resp = sess.get(TORRENT_URL, timeout=5)

                if 'ERROR LOADING CONTENT' in resp.text:
                    trys += 1
                    time.sleep(1)
                    self.logger.debug('Retry {}'.format(trys))
                else:
                    ok = True
        except:
            self.logger.error('Failed loading from {}'.format(TORRENT_URL))
            return

        if 'Site maintenance in process' in resp.text:
            self.logger.error('KAT down for maintenance {}'.format(TORRENT_URL))
            return

        try:
            soup = bs4.BeautifulSoup(resp.text, 'html.parser')

        except:
            self.logger.error('Failed parsing HTML at {}'.format(TORRENT_URL))
            return

        # find highest race number in HTML
        for elem in soup.select('div.torrents_table__torrent_name'):
            title = elem.select('a.torrents_table__torrent_title')[0].text

            if 'Formula 1' in title and str(CURRENT_SEASON) in title and 'SkyF1HD 1080p50' in title:
                race_number = int(title[15:17])

                # store for next time
                if CURRENT_SEASON > data.get('current_season', 0) or race_number > data.get('latest_race', 0):
                    data['current_season'] = CURRENT_SEASON
                    data['latest_race'] = race_number

        # create formatted race_id
        race_id = '{}x{:02d}'.format(CURRENT_SEASON, data['latest_race'])
        self.logger.info('Latest race: {}'.format(race_id))

        # iterate results for current race_id
        for elem in soup.select('div.torrents_table__torrent_name'):
            title = elem.select('a.torrents_table__torrent_title')[0].text

            if 'Formula 1' in title and str(CURRENT_SEASON) in title and 'SkyF1HD 1080p50' in title:

                if (not 'Race' in title and not 'Qualifying' in title) or 'Teds' in title:
                    self.logger.debug('Skipped: {}'.format(title))
                    continue

                magnet = elem.select(
                    'div.torrents_table__actions'
                )[0].find('a', {'title': 'Torrent magnet link'}).attrs['href']

                self.logger.debug('Found: {}'.format(magnet))

                if race_id not in data['races']:
                    data['races'][race_id] = dict()

                event = 'r' if 'Race' in title else 'q'

                if event not in data['races'][race_id]:
                    data['races'][race_id][event] = {
                        'title': title.replace(' ', '.'),
                        'magnet': magnet,
                        'added_to_rtorrent': False,
                    }


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
