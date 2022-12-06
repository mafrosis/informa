import os
import logging

from informa.lib import app
from informa.plugins import dans


logger = logging.getLogger('informa')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.INFO)

if os.environ.get('DEBUG'):
    logger.setLevel(logging.DEBUG)


def main():
    app.run()
