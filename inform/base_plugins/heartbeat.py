from . import InformBasePlugin

from .. import app

from datetime import timedelta

import yaml


class HeartbeatPlugin(InformBasePlugin):
    run_every = timedelta(weeks=1)

    def process(self):
        # dump all plugin data for a heartbeat alert
        alert_data = {}
        for m in app.config['plugins'].keys():
            alert_data[m] = app.config['plugins'][m].load()
        return yaml.dump(alert_data)
