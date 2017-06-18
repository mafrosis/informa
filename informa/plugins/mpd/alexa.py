import itertools

from flask import current_app as app
from flask_ask import statement, question

from .decorators import mpd
from informa.lib.alexa.decorators import alexa_validate


ALEXA_APP_ID = 'amzn1.ask.skill.cfa6b04c-12b0-4cb1-86e9-96bdc5722ac2'


#MPD_SEARCH_TERM_MAPPING = {
#    'artist': 'albumartist',
#    'album': 'album',
#}


@app.ask.intent('Playlist', mapping={'playlist': 'style'})
@alexa_validate(ALEXA_APP_ID)
@mpd
def add_and_play_playlist(client, playlist):
    if client is None:
        return statement("I couldn't connect to m.p.d.")

    # query MPD for playlists
    if playlist not in [p['playlist'] for p in client.listplaylists()]:
        return statement("I couldn't find a playlist called that")

    client.clear()
    client.load(playlist)
    client.play(0)

    return statement('Done')


@app.ask.intent('FindArtist', mapping={'text': 'Artist'})
@alexa_validate(ALEXA_APP_ID)
@mpd
def find_artist(client, text):
    # query MPD's API
    data = client.search('albumartist', text)

    # convert to dict of album names with track count
    data = {album: len(list(items)) for album, items in itertools.groupby(data, lambda x: x['album'])}

    if not data:
        return statement("I couldn't find any artists matching that")

    last = None

    # remove last item to build nice sentence
    if len(data) > 1:
        last_album = list(data.keys())[-1]
        last = (last_album, data.pop(last_album),)

    text = 'I found '
    for album, tracks in data.items():
        text += '{} with {} tracks, '.format(album, tracks)

    if last:
        text = text[:-2]
        text += ' and {} with {} tracks, '.format(*last)
    return statement(text[:-2])


@app.ask.intent('FindAlbum', mapping={'text': 'Album'})
@alexa_validate(ALEXA_APP_ID)
@mpd
def find_album(client, text):
    # query MPD's API
    data = client.search('album', text)

    # convert to dict of album names with track count
    data = {album: len(list(items)) for album, items in itertools.groupby(data, lambda x: x['album'])}

    if not data:
        return statement("I couldn't find any albums matching that")

    last = None

    # remove last item to build nice sentence
    if len(data) > 1:
        last_album = list(data.keys())[-1]
        last = (last_album, data.pop(last_album),)

    text = 'I found '
    for album, tracks in data.items():
        text += '{} with {} tracks, '.format(album, tracks)

    if last:
        text = text[:-2]
        text += ' and {} with {} tracks, '.format(*last)
    return question(text[:-2])


#@mpd
#def _find(client, search_type, search_text):
#    # query MPD's API
#    data = client.search(MPD_SEARCH_TERM_MAPPING[search_type], search_text)
#
#    # convert to dict of album names with track count
#    data = {album: len(list(items)) for album, items in itertools.groupby(data, lambda x: x['album'])}
#
#    if not data:
#        return statement("I couldn't find any artists matching that")
#
#    last = None
#
#    # remove last item to build nice sentence
#    if len(data) > 1:
#        last_album = list(data.keys())[-1]
#        last = (last_album, data.pop(last_album),)
#
#    text = 'I found '
#    for album, tracks in data.items():
#        text += '{} with {} tracks, '.format(album, tracks)
#
#    if last:
#        text = text[:-2]
#        text += ' and {} with {} tracks, '.format(*last)
#    return statement(text[:-2])
