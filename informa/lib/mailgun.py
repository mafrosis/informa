import logging
import os
from typing import Dict, Union

from jinja2 import Environment, FileSystemLoader
import requests

from informa.exceptions import MailgunKeyMissing, MailgunSendFailed


def send(
        logger: Union[logging.Logger, logging.LoggerAdapter],
        subject: str,
        template: str,
        content: Dict[str, str]
    ):
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
        content:   K/V data mapping to render template
    '''
    if os.environ.get('DEBUG'):
        logger.debug('Skip Mailgun send due to DEBUG')
        return

    try:
        api_key = os.environ['MAILGUN_KEY']
    except:
        raise MailgunKeyMissing

    env = Environment(loader=FileSystemLoader('templates'))

    if not template.endswith('.tmpl'):
        template += '.tmpl'

    with open(f'templates/{template}', encoding='utf-8') as f:
        body = env.from_string(f.read()).render(**content)

    # send the email via Mailgun's API
    resp = requests.post(
        'https://api.eu.mailgun.net/v2/mailgun.mafro.net/messages',
        auth=('api', api_key),
        data={
            'from': 'Informa <dev@mafro.net>',
            'to': 'forums@mafro.net',
            'subject': subject,
            'text': body,
            'html': body,
        },
        timeout=10,
    )
    if not bool(resp.status_code >= 200 and resp.status_code < 300):
        raise MailgunSendFailed
