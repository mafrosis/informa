import datetime
import logging
import os
import pathlib
from dataclasses import dataclass
from enum import Enum

import click
import googleapiclient
import httplib2
from jinja2 import Environment, FileSystemLoader
import pytz
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from gcsa.google_calendar import GoogleCalendar
from google.oauth2.service_account import Credentials
from PIL import Image
from playwright.sync_api import sync_playwright

from informa.lib import (
    ConfigBase,
    PluginAdapter,
    StateBase,
    app,
)
from informa.lib import fastapi as app_fastapi
from informa.lib.plugin import load_run_persist

logger = PluginAdapter(logging.getLogger('informa'))


router = APIRouter(prefix='/kindle-gcal')


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


@app.task('every 12 hours', name=__name__)
def run():
    load_run_persist(logger, StateBase, main)


def main(_: State, config: Config):
    events = fetch_calendar(config.gcal_id)
    render(events)
    capture()


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
            start = 7.53
            duration = 0.5
            timestring = ''
        else:
            start = e.start.hour
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
            'height': (duration * 78),
            'top': int(88 + ((start - 8) * 77)),
        }

    # Handle events overlapping with any others
    for e in events:
        for other in events:
            if e is other:
                continue
            events_overlap(e, other)

    today = datetime.datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%B %d, %Y')

    # Render events into Jinja template
    env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
    html = env.get_template('kindle_gcal.tmpl').render(events=[render_event(e) for e in events], today=today)

    with open('/tmp/informa-kindle-gcal-index.html', 'w', encoding='utf8') as f:
        f.write(html)


def capture():
    'Capture a JPG of the rendered HTML calendar'
    with sync_playwright() as p:
        browser = p.chromium.launch()  # Or firefox, webkit
        page = browser.new_page()
        page.goto('http://informa.mafro.net/kindle-gcal/html')  # Served by Fast API below
        page.set_viewport_size({'height': 1024, 'width': 758})
        page.screenshot(path='/tmp/informa-kindle-gcal.png')
        browser.close()

        # Convert to 8-bit greyscale
        Image.open('/tmp/informa-kindle-gcal.png').convert('L').save('/tmp/informa-kindle-gcal-grey.png')


def fetch_calendar(gcal_id: str) -> list[Event] | None:
    '''
    Fetch a Google Calendar and return Event objects
    '''
    gsuite_creds = os.environ.get('GSUITE_OAUTH_CREDS')
    if not gsuite_creds:
        logger.error('No Google service account credentials')
        return None

    try:
        gc = GoogleCalendar(credentials=Credentials.from_service_account_file(os.environ.get('GSUITE_OAUTH_CREDS')))
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


@router.get('/html')
def serve_html():
    'Serve the HTML calendar for JPG capture by playwright'
    if pathlib.Path('/tmp/informa-kindle-gcal-index.html').exists():
        return FileResponse('/tmp/informa-kindle-gcal-index.html', media_type='text/html')

    raise HTTPException(status_code=404, detail='HTML calendar missing')


@router.get('/image')
def serve_image():
    'Serve the PNG calendar for Kindle to fetch periodically'
    if pathlib.Path('/tmp/informa-kindle-gcal-grey.png').exists():
        return FileResponse('/tmp/informa-kindle-gcal-grey.png', media_type='image/png')

    raise HTTPException(status_code=404, detail='Calendar PNG missing')


app_fastapi.include_router(router)


@click.group(name=__name__[16:].replace('_', '-'))
def cli():
    'Render a Google Calendar to a JPG for Kindle screensaver'
