{% import_yaml "default_vars.sls" as defaults %}

flask_debug: true
secret_key: ssh_its_a_secret
zapier_email_webhook_id: ""

app_name: informa
app_user: {{ defaults.app_user }}
app_repo: mafrosis/informa
app_repo_rev: dev
login_user: {{ defaults.login_user }}

gunicorn_host: {{ defaults.gunicorn_host }}
gunicorn_port: {{ defaults.gunicorn_port }}

timezone: {{ defaults.timezone }}
hostname: informa
locale: {{ defaults.locale }}

rabbitmq_host: {{ defaults.rabbitmq_host }}
rabbitmq_vhost: {{ defaults.rabbitmq_vhost }}
rabbitmq_user: {{ defaults.rabbitmq_user }}
rabbitmq_pass: {{ defaults.rabbitmq_pass }}

# get dotfiles from github
github_username: {{ defaults.github_username }}

# install zsh and set as default login shell
shell: {{ defaults.shell }}

# install extras from apt and install dotfiles
extras:
{% for name in defaults.extras %}
  - {{ name }}
{% endfor %}

# install extras from pip
pip:
{% for name in defaults.pip %}
  - {{ name }}
{% endfor %}

# set backports to AU in bit.ly/19Nso9M
deb_mirror_prefix: {{ defaults.deb_mirror_prefix }}

github_key: |
