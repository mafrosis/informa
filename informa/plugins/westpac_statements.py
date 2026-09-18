import contextlib
import io
import logging
import os
import pathlib
from collections.abc import Iterator
from dataclasses import dataclass, field

import click
from transto.exceptions import MissingEnvVar

from informa import app
from informa.lib import PluginAdapter, StateBase, mailgun
from informa.lib.utils import raise_alarm
from transto import westpac

logger = PluginAdapter(logging.getLogger('informa'))


@dataclass
class State(StateBase):
    'Track which statement PDFs have been imported'

    imported: list[str] = field(default_factory=list)


@app.task('every 24 hours')
def run(plugin):
    plugin.execute()


def main(state: State) -> int:
    '''
    Import any new Westpac statement PDFs found in the mounted statements directory

    Args:
        state: Plugin state, tracking imported statement filenames

    Returns:
        Count of newly imported statements
    '''
    stmt_dir = pathlib.Path(os.environ.get('WESTPAC_STATEMENTS_DIR', './statements'))

    if not stmt_dir.is_dir():
        logger.warning('Westpac statements directory not found: %s', stmt_dir)
        return 0

    # Import unprocessed statements, oldest first
    pdfs = sorted(pdf for pdf in stmt_dir.glob('*.pdf') if pdf.name not in state.imported)
    count = 0

    for pdf in pdfs:
        if process_statement(pdf):
            state.imported.append(pdf.name)
            count += 1

    return count


def process_statement(pdf: pathlib.Path) -> bool:
    '''
    Import a single statement PDF via transto, emailing the transaction log

    Args:
        pdf: Path to the statement PDF

    Returns:
        True if the statement was imported successfully
    '''
    try:
        with capture_transto_logs() as log_stream, pdf.open('rb') as f:
            westpac.cc(f)

        logger.info('Imported statement %s', pdf.name)
        mailgun.send(logger, f'Westpac statement {pdf.name} imported', content=log_stream.getvalue())

    except (OSError, MissingEnvVar) as e:
        raise_alarm(logger, f'Westpac statement import failed: {pdf.name}', e)
        return False
    else:
        return True


@contextlib.contextmanager
def capture_transto_logs() -> Iterator[io.StringIO]:
    '''
    Capture logging from transto, emitting the logs as a StringIO

    Yields:
        StringIO containing any transto log output
    '''
    transto_logger = logging.getLogger('transto')
    transto_logger.setLevel(logging.INFO)

    log_stream = io.StringIO()
    log_handler = logging.StreamHandler(log_stream)
    log_handler.setLevel(logging.INFO)

    transto_logger.addHandler(log_handler)
    try:
        yield log_stream
    finally:
        # Always remove the handler, so repeated runs don't accumulate duplicates
        transto_logger.removeHandler(log_handler)


@click.group(name='westpac-statements')
def cli():
    'Westpac statement loader'
