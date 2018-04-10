import datetime

from .base import InformaBasePlugin
from ..lib.decorators import retry
from ..lib.rtorrent import RTorrent

HOST = 'jorg'
PORT = 5000


class RTorrentPlugin(InformaBasePlugin):
    run_every = datetime.timedelta(minutes=1)

    @retry(times=3, sleep=3)
    def process(self):
        rt = RTorrent(HOST, PORT)
        data = rt.get_torrents()

        if data is None:
            raise Exception

        return data
