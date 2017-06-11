from ..base import InformaBasePlugin
from . import alexa


class MpdPlugin(InformaBasePlugin):
    run_every = None


    def process(self):
        #stmt = alexa.find_artist('jan')
        #stmt = alexa.find_album('real')
        stmt = alexa.add_and_play_playlist('jazz')
        return str(stmt)
