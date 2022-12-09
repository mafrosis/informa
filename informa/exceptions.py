class MailgunKeyMissing(Exception):
    'Environment var MAILGUN_KEY is missing'

class MailgunSendFailed(Exception):
    'Mailgun email send failed!'
