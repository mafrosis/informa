import datetime
import logging
import traceback

from zoneinfo import ZoneInfo

from informa.lib import mailgun


def now_aest() -> datetime.datetime:
    'Utility function to return now as TZ-aware datetime'
    return datetime.datetime.now(ZoneInfo('Australia/Melbourne'))


def raise_alarm(logger: logging.Logger, msg: str, ex: Exception | None = None):
    'Log an error and send an email'
    if ex and logger.getEffectiveLevel() == logging.DEBUG:
        logger.exception(ex)
    else:
        logger.error(msg)

    # Send the traceback in the email body
    tb = None
    if ex:
        tb = '\n'.join(traceback.format_list(traceback.extract_tb(ex.__traceback__)))

    # Format message using PluginAdapter if available, otherwise use raw message
    if hasattr(logger, 'process'):
        fmtd_msg, _ = logger.process(msg)
    else:
        fmtd_msg = msg

    mailgun.send(logger, f'ERROR {fmtd_msg}', content=f'<pre>{tb}<br>{ex!s}</pre>')
