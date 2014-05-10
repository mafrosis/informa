# vim: set ft=jinja:

DEBUG = {{ pillar['flask_debug'] }}
SECRET_KEY = '{{ pillar['secret_key'] }}'

{% if 'zapier_email_webhook_id' in pillar %}
ZAPIER_EMAIL_WEBHOOK_ID = '{{ pillar['zapier_email_webhook_id'] }}'
ZAPIER_EMAIL_HEARTBEAT = True
{% endif %}

SQLALCHEMY_DATABASE_URI = 'sqlite:////srv/inform/inform.sqlitedb'
