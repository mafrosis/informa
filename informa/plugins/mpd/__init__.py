import datetime

from ..base import InformaBasePlugin
from . import alexa


class MpdPlugin(InformaBasePlugin):
    run_every = datetime.timedelta(seconds=15)

    def process(self):
        #stmt = alexa.find_artist('jan')
        #stmt = alexa.find_album('real')
        stmt = alexa.add_and_play_playlist('hiphop')
        return str(stmt)
