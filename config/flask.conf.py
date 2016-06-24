DEBUG = False
SECRET_KEY = 'ssh_its_a_secret'

# Celery config
BROKER_URL = 'redis://redis:6379'
CELERY_DEFAULT_QUEUE = 'informa'
CELERY_DEFAULT_EXCHANGE = 'informa'
CELERY_DEFAULT_EXCHANGE_TYPE = 'direct'
CELERY_DEFAULT_ROUTING_KEY = 'informa'

ZAPIER_EMAIL_WEBHOOK_ID = 'q9du3'
ZAPIER_EMAIL_HEARTBEAT = True

SQLALCHEMY_DATABASE_URI = 'sqlite:////srv/app/informa.sqlitedb'
