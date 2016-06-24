import datetime

from .base import InformaBasePlugin
from ..lib.rtorrent import RTorrent

HOST = '172.18.0.1'
PORT = 5000
RTORRENT_XMLRPC = 'scgi://{}:{}'.format(HOST, PORT)


class RTorrentPlugin(InformaBasePlugin):
    run_every = datetime.timedelta(minutes=1)

    def process(self):
        rt = RTorrent(HOST, PORT)
        data = rt.get_torrents()
        self.store(data)
        return data
