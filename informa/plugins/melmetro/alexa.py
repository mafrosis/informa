import datetime

import humanize
import pytz
import requests

from flask import abort, request
from flask import current_app as app
from flask_ask import statement

from . import exceptions


ALEXA_APP_ID = 'amzn1.ask.skill.64868ca7-150d-4fe5-bdd0-033b88157da3'


URL = "https://www.ptv.vic.gov.au/langsing/stop-services?stopId={stopId}&direction={direction}&limit=3&mode=1"

ROUTES = {
    96: {
        'stopId': 10002960,
        'directions': {
            'brunswick': 'East Brunswick',
            'east brunswick': 'East Brunswick',
            'st kilda': 'St Kilda Beach',
            'st kilda beach': 'St Kilda Beach',
        },
        'default': 'St Kilda Beach',
    },
    12: {
        'stopId': 10002553,
        'directions': {
            'victoria gardens': 'Victoria Gardens',
            'st kilda': 'St Kilda (Fitzroy St)',
            'st kilda beach': 'St Kilda (Fitzroy St)',
            'fitzroy street': 'St Kilda (Fitzroy St)',
        },
        'default': 'St Kilda',
    }
}


@app.ask.intent('NextTram',
    mapping={'line': 'Number', 'direction': 'Destination'},
    convert={'line': int}
)
def melmetro(line, direction):
    if request.json['session']['application']['applicationId'] != ALEXA_APP_ID:
        abort(403)

    if not line:
        if not direction:
            abort(400)

        # if line not supplied, determine lines for the destination
        lines = [
            ln for ln, data in ROUTES.items()
            if direction.lower() in ROUTES[ln]['directions'].keys()
        ]
    else:
        lines = [line]

        # use default destination if none supplied
        if not direction:
            direction = ROUTES[line]['default']

    #print(request.headers)
    #print(json.dumps(request.json, indent=2))

    data = {}

    for line in lines:
        try:
            data[line] = query_ptv(line, direction.lower(), asdatetime=True)
        except exceptions.APIError:
            return statement('Unfortunately the VIC A.P.I. is not working right now')
        except exceptions.UnknownDestinationError:
            return statement("I'm sorry I don't know that destination")

    # determine local time in Melbourne
    local_tz = pytz.timezone('Australia/Melbourne')
    now = local_tz.normalize(
        pytz.utc.localize(datetime.datetime.utcnow()).astimezone(local_tz)
    )

    text = ''

    print(data[12])

    # generate Alexa reply for each train line
    for line, trains in data.items():
        if trains['next_trains']:
            times = []
            for t in trains['next_trains']:
                time_str = humanize.naturaltime(now - t)[:-9]
                times.append(time_str)

            # make unique; maintain list order
            times = sorted(set(times), key=lambda x: times.index(x))

            # convert to friendly text
            if len(times) > 1:
                last_time = times[-1]
                times = times[:-1]
                text += 'The {} comes in {} and {}. '.format(
                    line, ', '.join(times), last_time
                )
            else:
                text += 'The {} comes in {}. '.format(line, times[0])

    if text:
        return statement(text)
    else:
        return statement('Boo. No trains found')


def query_ptv(line=None, direction=None, asdatetime=False):
    try:
        # retrieve valid destination
        direction = ROUTES[line]['directions'][direction]
    except KeyError:
        return statement("I'm sorry I don't know that destination")

    try:
        resp = requests.get(
            URL.format(stopId=ROUTES[line]['stopId'], direction=direction)
        )
        print(
            URL.format(stopId=ROUTES[line]['stopId'], direction=direction)
        )
    except:
        raise exceptions.APIError('Failed loading from ptv.vic.gov.au')

    try:
        trains = resp.json()['values']
    except:
        raise exceptions.APIError('Bad JSON response from ptv.vic.gov.au')

    try:
        ## tag trains as express/normal
        #for t in trains:
        #    if t['run']['num_skipped'] == EXPRESS_TRAIN_STATION_SKIP_FILTER:
        #        express = True
        #    else:
        #        express = False
        #    t.update({'express': express})

        # NOTE API's direction parameter doesn't always work
        # filter here for the trains going to our destination
        if len(trains) > 1:
            trains = [
                t for t in trains
                if t['platform']['direction']['direction_name'] == direction
            ]

        data = {'next_trains': []}

        # convert all the UTC to local time
        local_tz = pytz.timezone('Australia/Melbourne')

        for t in trains:
            # parse train time
            utc_train_time = datetime.datetime.strptime(
                t['time_realtime_utc'], '%Y-%m-%dT%H:%M:%SZ'
            )
            # convert to local time, normalizing for DST
            local_train_time = local_tz.normalize(
                pytz.utc.localize(utc_train_time).astimezone(local_tz)
            )

            # build output
            data['next_trains'].append(
                local_train_time if asdatetime else local_train_time.strftime('%Y-%m-%d %H:%M')
            )

    except Exception as e:
        raise exceptions.APIError('Failed parsing JSON into train times: {}'.format(e))

    return data
