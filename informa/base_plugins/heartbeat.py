from . import InformaBasePlugin

from datetime import timedelta

import yaml


class HeartbeatPlugin(InformaBasePlugin):
    run_every = timedelta(weeks=1)

    def process(self):
        # dump plugin data for a heartbeat alert
        alert_data = {
            self.friendly_name: self.load()
        }
        return yaml.dump(alert_data)
