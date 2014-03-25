include:
  - gunicorn
  - github
  - logs
  - nginx
  - rabbitmq
  - supervisor
  - virtualenv-base

extend:
  supervisor:
    pip.installed:
      - require:
        - virtualenv: app-virtualenv

/srv/inform:
  file.directory:
    - user: {{ pillar['app_user'] }}
    - group: {{ pillar['app_user'] }}
    - makedirs: true
    - require_in:
      - git: git-clone-app

git-clone-app:
  git.latest:
    - name: git@github.com:mafrosis/inform.git
    - target: /srv/inform
    - runas: {{ pillar['app_user'] }}
    - require:
      - pkg: git
      - file: github.pky

app-virtualenv:
  virtualenv.managed:
    - name: /home/{{ pillar['app_user'] }}/.virtualenvs/{{ pillar['app_name'] }}
    - requirements: /srv/inform/config/requirements.txt
    - user: {{ pillar['app_user'] }}
    - require:
      - pip: virtualenv-init-setuptools
      - git: git-clone-app

/etc/supervisor/conf.d/inform.conf:
  file.managed:
    - source: salt://inform/supervisord.conf
    - template: jinja
    - defaults:
        purge: false
        app_user: {{ pillar['app_user'] }}
    - require:
      - user: {{ pillar['app_user'] }}
      - cmd: rabbitmq-server-running
    - require_in:
      - service: supervisor

inform-service:
  supervisord.running:
    - name: "inform:"
    - update: true
    - require:
      - service: supervisor
    - watch:
      - file: /etc/supervisor/conf.d/inform.conf
      - file: /etc/gunicorn.d/{{ pillar['app_name'] }}.conf.py

memcached:
  pkg.installed

/etc/nginx/sites-available/inform.conf:
  file.managed:
    - source: salt://inform/nginx.conf
    - template: jinja
    - context:
        gunicorn_host: {{ pillar['gunicorn_host'] }}
        gunicorn_port: {{ pillar['gunicorn_port'] }}
    - require:
      - pkg: nginx

/etc/nginx/sites-enabled/inform.conf:
  file.symlink:
    - target: /etc/nginx/sites-available/inform.conf
    - require:
      - file: /etc/nginx/sites-available/inform.conf
