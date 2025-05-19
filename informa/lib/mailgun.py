import logging
import os
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader

from informa.exceptions import MailgunKeyMissing, MailgunSendFailed, MailgunTemplateFail
from informa.lib import PluginAdapter


def send(
    logger: logging.Logger | PluginAdapter,
    subject: str,
    template: str | None = None,
    content: str | dict[str, Any] | None = None,
):
    '''
    Handle plugin loggers, and any exceptions raised during _send
    '''
    if logger.getEffectiveLevel() == logging.DEBUG:
        logger.debug('Skip Mailgun send due to DEBUG')
        return False

    _send(subject, template, content)


def _send(subject: str, template: str | None = None, content: str | dict[str, Any] | None = None):
    '''
    Send an email via Mailgun

    curl -s --user 'api:YOUR_API_KEY' \
        https://api.mailgun.net/v2/YOUR_DOMAIN_NAME/messages \
        -F from='Excited User <YOU@YOUR_DOMAIN_NAME>' \
        -F to='foo@example.com' \
        -F subject='Hello' \
        -F text='Testing some Mailgun awesomness!' \
        --form-string html='<html>HTML version of the body</html>'

    Params:
        subject:   Email subject line
        template:  The jinja2 template filename in templates/
        content:   K/V data mapping to render template, OR raw string for body
    '''
    try:
        api_key = os.environ['MAILGUN_KEY']
    except KeyError as e:
        raise MailgunKeyMissing from e

    env = Environment(loader=FileSystemLoader('templates'), autoescape=True)

    if template:
        if not content:
            raise MailgunTemplateFail

        if not template.endswith('.tmpl'):
            template += '.tmpl'

        with open(f'templates/{template}', encoding='utf-8') as f:
            body = env.from_string(f.read()).render(**content)

    elif isinstance(content, str):
        body = content
    else:
        body = subject

    # send the email via Mailgun's API
    resp = requests.post(
        'https://api.eu.mailgun.net/v2/mailgun.mafro.net/messages',
        auth=('api', api_key),
        data={
            'from': 'Informa <informa@mafro.net>',
            'to': 'informa@mafro.net',
            'subject': subject,
            'text': body,
            'html': body,
        },
        timeout=10,
    )
    if not bool(resp.status_code >= 200 and resp.status_code < 300):  # noqa: PLR2004
        raise MailgunSendFailed(resp.json().get('message', ''))
