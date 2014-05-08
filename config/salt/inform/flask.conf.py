# vim: set ft=jinja:

DEBUG = {{ pillar['flask_debug'] }}

{% if 'zapier_email_webhook_id' in pillar %}
ZAPIER_EMAIL_WEBHOOK_ID = '{{ pillar['zapier_email_webhook_id'] }}'
{% endif %}
