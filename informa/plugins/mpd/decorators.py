import functools

import mpd as libmpd


def mpd(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        client = libmpd.MPDClient()
        try:
            client.connect('127.0.0.1', 6600)
            return f(client, *args, **kwargs)
        finally:
            client.close()
            client.disconnect()
    return wrapped
