#import datetime
import os
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
WATCH_DIR = '/watch'


class F1Plugin(InformaBasePlugin):
    run_every = crontab(minute='*/15')

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

        self._check_for_new(data)
        self._magnet_to_torrent(data)

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

                # disable first and last parts for qualy
                if 'Qualifying' in torrent_data['name']:
                    rt.set_file_priority(hash_id, 0, 0)
                    rt.set_file_priority(hash_id, 2, 0)
                    self.logger.info('Disabled pre/post-qualifying on {}'.format(torrent_data['name']))

                # disable last part for race
                if 'Race' in torrent_data['name']:
                    rt.set_file_priority(hash_id, 2, 0)
                    self.logger.info('Disabled post-race on {}'.format(torrent_data['name']))


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
                if 'Race' in title or 'Qualifying' in title:
                    try:
                        ok = False
                        trys = 0

                        sess = requests.Session()
                        url = 'https://katcr.co/min/torrent/{}/{}.html'.format(
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
                            # TODO couldnt parse magnet failure
                            continue

                        if race_id not in data['races']:
                            data['races'][race_id] = dict()

                        data['races'][race_id]['r' if 'Race' in title else 'q'] = {
                            'title': title,
                            'url': url,
                            'magnet': magnet,
                            'added_to_rtorrent': False,
                        }
                    except:
                        self.logger.error('Failed loading from {}'.format(item['page_link']))


    def _magnet_to_torrent(self, data):
        '''
        Convert any stored magnet links into real torrent files in /watch
        '''
        if not os.path.exists('/watch'):
            self.logger.error('No /watch directory!')
            return

        for race_id, stages in data['races'].items():
            for stage, race_data in stages.items():
                if race_data['added_to_rtorrent'] is False:
                    rt = RTorrent(RTORRENT_HOST, 5000)
                    self.logger.info(race_data['magnet'])
                    rt.add_magnet(race_data['magnet'])

                    # parse magnet link to create torrent filename
                    qs = urlparse(race_data['magnet']).query.split('&')
                    filename = next((p[3:] for p in qs if p.startswith('dn=')), '')
                    hash_ = qs[0][12:]

                    self.logger.debug("Calling magnet to torrent for '{}'".format(filename))

                    # convert magnet links to torrent file via API
                    resp = requests.post(
                        'http://magnet2torrent.com/upload/',
                        headers={
                            'User-Agent': 'Mozilla/5.0'
                        },
                        data={
                            'magnet': race_data['magnet']
                        }
                    )
                    # write torrent into watch dir
                    with open(os.path.join(WATCH_DIR, 'magnet-{}-{}.torrent'.format(filename, hash_)), 'wb') as f:
                        f.write(resp.content)

                    self.logger.info('MAGNET torrent for {}'.format(filename))
                    race_data['added_to_rtorrent'] = True

                    # hang for rtorrent to pick up watched torrents
                    time.sleep(20)
