from ..base_plugins import InformBasePlugin

from datetime import timedelta
from itertools import groupby

import datetime
import pytz
import requests


URL = "http://ptv.vic.gov.au/transport/direct/chronos.php?stopId={}"
STATION_ID = 10001118

# Malvern to City express skips 3 stations
EXPRESS_TRAIN_STATION_SKIP_FILTER = 3


class MelMetroPlugin(InformBasePlugin):
    run_every = timedelta(minutes=1)
    plugin_name = "melmetro"

    local_tz = pytz.timezone('Australia/Melbourne')

    def process(self):
        try:
            r = requests.get(URL.format(STATION_ID))
        except:
            print "Failed loading from ptv.vic.gov.au"
            return {}

        try:
            trains = r.json()
        except:
            print "Bad JSON response from ptv.vic.gov.au"
            return {}

        try:
            # filter for only trains heading to the city
            trains = [t for t in trains['values'] if t['platform']['direction']['direction_id'] == 0]

            # tag trains as express/normal
            for t in trains:
                if t['run']['num_skipped'] == EXPRESS_TRAIN_STATION_SKIP_FILTER:
                    express = True
                else:
                    express = False
                t.update({'express': express})

            data = {'trains': []}

            for i in xrange(0,15):
                # parse train time
                utc_train_time = datetime.datetime.strptime(trains[i]['time_timetable_utc'], '%Y-%m-%dT%H:%M:%SZ')

                # convert time from UTC into local time, normalizing for DST
                local_train_time = self.local_tz.normalize(
                    pytz.utc.localize(utc_train_time).astimezone(self.local_tz)
                )

                # build output
                data['trains'].append({
                    'time': local_train_time.strftime('%Y-%m-%dT%H:%M:%S.%f%z'),
                    'express': trains[i]['express'],
                })

            # group trains by departure time (duplicates are included due to upstream merged train lines)
            data['trains'] = [
                {time: list(group)[0]['express']}
                for time, group in groupby(data['trains'], lambda t: t['time'])
            ]

        except Exception:
            print 'Failed parsing JSON into train times: "{}"'.format(self.format_excp())
            return {}

        self.store(data)
        return data
