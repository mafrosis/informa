include:
  - app.virtualenv
  - app.source
  - app.supervisor
  - gunicorn
  - nginx.config

extend:
  supervisor:
    pip.installed:
      - require:
        - virtualenv: app-virtualenv

  app-virtualenv:
    virtualenv.managed:
      - requirements: /srv/informa/config/requirements.txt
      - require:
        - git: git-clone-app

  informa-supervisor-service:
    supervisord.running:
      - watch:
        - file: /etc/supervisor/conf.d/informa.conf
        - file: /etc/gunicorn.d/informa.conf.py

  gunicorn-config:
    file.managed:
      - context:
          gunicorn_port: {{ pillar['gunicorn_port'] }}
          workers: 1
          timeout: 60

  {% if grains.get('env', '') == 'prod' %}
  /etc/nginx/sites-available/informa.conf:
    file.managed:
      - context:
          server_name: {{ pillar['hostname'] }}
          root: /srv/informa
  {% endif %}


flask-app-config:
  file.managed:
    - name: /srv/informa/informa/flask.conf.py
    - source: salt://informa/flask.conf.py
    - template: jinja
    - user: {{ pillar['app_user'] }}
    - group: {{ pillar['app_user'] }}
    - require:
      - git: git-clone-app
    - require_in:
      - service: supervisor

sqlite3:
  pkg.installed

sqlalchemy-init:
  cmd.run:
    - name: /home/{{ pillar['app_user'] }}/.virtualenvs/informa/bin/python manage.py init_db
    - unless: test -f /srv/informa/informa.sqlitedb
    - cwd: /srv/informa
    - user: {{ pillar['app_user'] }}
    - require:
      - pkg: sqlite3
      - file: flask-app-config
    - require_in:
      - service: supervisor

memcached:
  pkg.installed
