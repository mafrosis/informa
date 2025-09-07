import asyncio
import datetime
import logging
import os
import pathlib
import tempfile
from dataclasses import dataclass
from enum import Enum

import click
import googleapiclient
import httplib2
import pytz
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from gcsa.google_calendar import GoogleCalendar
from google.oauth2.service_account import Credentials
from jinja2 import Environment, FileSystemLoader
from PIL import Image
from playwright.async_api import async_playwright
from rocketry.conds import every, time_of_day

from informa import app
from informa.lib import (
    ConfigBase,
    PluginAdapter,
    StateBase,
)
from informa.lib.plugin import load_config, load_run_persist

logger = PluginAdapter(logging.getLogger('informa'))


router = APIRouter(prefix='/kindle-gcal')


@app.api(router)
def fastapi():
    # Register the APIRouter with Informa
    pass


class Offset(Enum):
    LEFT = 1
    RIGHT = 2


@dataclass
class State(StateBase):
    pass


@dataclass
class Config(ConfigBase):
    gcal_id: str


@dataclass
class Event:
    start: datetime.datetime | None
    end: datetime.datetime | None
    title: str | None
    location: str | None
    offset: Offset | None = None

    @property
    def duration(self) -> datetime.timedelta | None:
        if not self.start:
            return None
        return self.end - self.start


@app.task(
    (every('15 mins') & time_of_day.between('07:00', '17:00'))
    | (every('2 hours') & time_of_day.between('17:00', '07:00'))
)
def run():
    load_run_persist(logger, StateBase, main)


def main(_: State, config: Config) -> int:
    tasks = set()

    # Fetch events
    events = fetch_calendar(config.gcal_id)
    if events is not None:
        # Render HTML calendar
        render(events)

        # Capture calendar as JPEG via coroutine
        t = asyncio.ensure_future(capture())
        tasks.add(t)
        t.add_done_callback(tasks.discard)

        return len(events)
    return 0


def get_tmpdir() -> str:
    'Fetch the current tmpdir, creating if missing'
    if getattr(app.fastapi.state, 'data', None):
        if __name__ not in app.fastapi.state.data:
            # Create if unset
            app.fastapi.state.data = {__name__: {'tmpdir': tempfile.TemporaryDirectory()}}
        logger.debug(app.fastapi.state.data[__name__]['tmpdir'].name)
        return app.fastapi.state.data[__name__]['tmpdir'].name
    tmpdir = tempfile.gettempdir()
    logger.debug(tmpdir)
    return tmpdir


def render(events: list[Event]):
    'Render events to HTML'

    def events_overlap(a: Event, b: Event):
        'Check if two events overlap in time'
        if a.offset is not None or b.offset is not None:
            return
        if a.start is None and b.start is None:
            # Two all-day events
            a.offset = Offset.LEFT
            b.offset = Offset.RIGHT
        elif a.start is None or b.start is None:
            # Only one event is all-day
            return
        elif (a.start < b.end) and (a.end > b.start):
            a.offset = Offset.LEFT
            b.offset = Offset.RIGHT

    def render_event(e: Event) -> dict:
        if e.start is None:
            # All day event
            start = 7.22
            duration = 0.69
            timestring = ''
        else:
            start = e.start.hour + (e.start.minute / 60)
            duration = e.duration.total_seconds() / 3600
            timestring = f'{e.start.strftime("%-I:%M %p")} - {e.end.strftime("%-I:%M %p")}'

        # Default title to timestring if blank
        if not e.title:
            e.title = timestring
            timestring = ''

        # Don't render timestring for short events
        if e.duration and e.duration < datetime.timedelta(hours=1):
            timestring = ''

        # Adjust width and left position if overlapping
        width = 330 if e.offset else 660
        left = 430 if e.offset == Offset.RIGHT else 100

        return {
            'name': e.title,
            'location': timestring,
            'width': width,
            'left': left,
            'height': (duration * 76),
            'top': int(105 + ((start - 8) * 73)),
        }

    # Handle events overlapping with any others
    for e in events:
        for other in events:
            if e is other:
                continue
            events_overlap(e, other)

    today = datetime.datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%B %d, %Y')

    # Render events into Jinja template
    env = Environment(loader=FileSystemLoader(os.environ.get('TEMPLATE_DIR', './templates')), autoescape=True)
    html = env.get_template('kindle_gcal.tmpl').render(events=[render_event(e) for e in events], today=today)

    tmpdir = get_tmpdir()

    with open(f'{tmpdir}/informa-kindle-gcal-index.html', 'w', encoding='utf8') as f:
        f.write(html)


async def capture():
    '''
    Capture a JPG of the rendered HTML calendar. Required to run async to support using Playwright
    from Rocketry coroutine event loop.
    '''
    tmpdir = get_tmpdir()

    async with async_playwright() as p:
        browser = await p.chromium.launch()  # Or firefox, webkit
        page = await browser.new_page()
        await page.goto('http://localhost:3000/kindle-gcal/html')  # Served by Fast API below
        await page.set_viewport_size({'height': 1024, 'width': 758})
        await page.screenshot(path=f'{tmpdir}/informa-kindle-gcal.png')
        await browser.close()

        # Convert to 8-bit greyscale
        Image.open(f'{tmpdir}/informa-kindle-gcal.png').convert('L').save(f'{tmpdir}/informa-kindle-gcal-grey.png')


def fetch_calendar(gcal_id: str) -> list[Event] | None:
    '''
    Fetch a Google Calendar and return Event objects
    '''
    gsuite_creds = os.environ.get('GSUITE_OAUTH_CREDS')
    if not gsuite_creds:
        logger.error('No Google service account credentials')
        return None

    try:
        gc = GoogleCalendar(credentials=Credentials.from_service_account_file(gsuite_creds))
    except googleapiclient.errors.HttpError:
        logger.error('Failed to authenticate to Google Calendar API')
        return None

    today = datetime.datetime.now(tz=pytz.timezone('Australia/Melbourne')).date()

    try:
        gcal_events = gc.get_events(
            calendar_id=gcal_id,
            time_min=today,
            time_max=today + datetime.timedelta(days=1),
            single_events=True,
            order_by='startTime',
        )

    except (httplib2.error.ServerNotFoundError, TimeoutError):
        logger.error('Failed fetching calendar data (timeout or server not found)')
        return None

    events = []

    for ev in gcal_events:
        if isinstance(ev.start, datetime.datetime):
            # Timed events
            event = Event(
                start=ev.start.astimezone(pytz.timezone(ev.timezone)),
                end=ev.end.astimezone(pytz.timezone(ev.timezone)),
                location=ev.location,
                title=ev.summary,
            )
        else:
            # All day events
            event = Event(start=None, end=None, location=ev.location, title=ev.summary)

        events.append(event)

    return events


@app.fastapi.on_event('startup')
def startup_event():
    'Create a temp directory in which to store generated files'
    tmpdir = get_tmpdir()
    logger.debug('New temporary directory created %s', tmpdir)


@app.fastapi.on_event('shutdown')
def shutdown_event():
    'Cleanup the temp directory'
    try:
        tmpdir = app.fastapi.state.data[__name__]['tmpdir']
        tmpdir.cleanup()
        logger.debug('Temporary directory cleaned up %s', tmpdir.name)
    except AttributeError:
        pass


@router.get('/html')
def serve_html():
    'Serve the HTML calendar for JPG capture by playwright'
    tmpdir = get_tmpdir()

    if pathlib.Path(f'{tmpdir}/informa-kindle-gcal-index.html').exists():
        return FileResponse(f'{tmpdir}/informa-kindle-gcal-index.html', media_type='text/html')

    raise HTTPException(status_code=404, detail='HTML calendar missing')


@router.get('/image')
def serve_image():
    'Serve the PNG calendar for Kindle to fetch periodically'
    tmpdir = get_tmpdir()

    if pathlib.Path(f'{tmpdir}/informa-kindle-gcal-grey.png').exists():
        return FileResponse(f'{tmpdir}/informa-kindle-gcal-grey.png', media_type='image/png')

    raise HTTPException(status_code=404, detail='Calendar PNG missing')


@click.group(name=__name__[16:].replace('_', '-'))
def cli():
    'Render a Google Calendar to a JPG for Kindle screensaver'


@cli.command('render')
def render_():
    config = load_config(Config)
    events = fetch_calendar(config.gcal_id)
    if events is not None:
        render(events)


@cli.command('capture')
def capture_():
    asyncio.run(capture())
