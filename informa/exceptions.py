class AppError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)

    def __str__(self):
        if self.message:
            return f'{self.__doc__} ({self.message})'
        return str(self.__doc__)


class StateJsonDecodeError(AppError):
    'Unable to decode plugin state JSON'


class MailgunKeyMissing(AppError):
    'Environment var MAILGUN_KEY is missing. Are you running in DEBUG?'


class MailgunTemplateFail(AppError):
    'Mailgun template supplied without content'


class MailgunSendFailed(AppError):
    'Mailgun email send failed!'


class ReachedLastSeen(AppError):
    'Reached a value already seen in previous run'
