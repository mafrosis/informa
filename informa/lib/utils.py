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
    logger.error(msg)

    # Send the traceback in the email body
    tb = None
    if ex:
        tb = '\n'.join(traceback.format_list(traceback.extract_tb(ex.__traceback__)))

    fmtd_msg, _ = logger.process(msg)
    mailgun.send(logger, f'ERROR {fmtd_msg}', content=f'<pre>{tb}</pre>')
