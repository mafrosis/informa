import functools
import time


def retry(times, sleep=0):
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            """
            Retry method N number of times.

            - Expects Exception to indicate called method failure.
            - The most recent Exception is re-raised if no success.
            """
            retry = 0

            while retry < times:
                last_error = None
                try:
                    ret = f(*args, **kwargs)
                    break
                except Exception as e:
                    last_error = e
                retry += 1
                time.sleep(sleep)

            if last_error is not None:
                raise last_error

            return ret

        return wrapped
    return decorator
