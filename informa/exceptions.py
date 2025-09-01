class AppError(Exception):
    def __init__(self, message: str = ''):
        self.message = message
        super().__init__(message)

    def __str__(self):
        if self.message:
            return f'{self.__doc__} ({self.message})'
        return str(self.__doc__)


class StateJsonDecodeError(AppError):
    'Unable to decode plugin state JSON'


class PluginError(AppError):
    def __init__(self, plugin_name):
        self.plugin_name = plugin_name

    def __str__(self):
        return self.__doc__.format(self.plugin_name)

class PluginAlreadyEnabled(PluginError):
    'Plugin {} already enabled'

class PluginAlreadyDisabled(PluginError):
    'Plugin {} already disabled'


class MailgunKeyMissing(AppError):
    'Environment var MAILGUN_KEY is missing. Are you running in DEBUG?'


class MailgunTemplateFail(AppError):
    'Mailgun template supplied without content'


class MailgunSendFailed(AppError):
    'Mailgun email send failed!'
