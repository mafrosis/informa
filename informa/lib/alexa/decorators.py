import functools

from flask import abort, has_request_context, request


def alexa_validate(alexa_app_id):
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if has_request_context() and request.json['session']['application']['applicationId'] != alexa_app_id:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
