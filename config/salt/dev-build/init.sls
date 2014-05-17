include:
  - tmux-segments

extend:
  gunicorn-config:
    file.managed:
      - context:
          gunicorn_port: {{ pillar['gunicorn_port'] }}
          loglevel: debug

  supervisor-log-dir:
    file.directory:
      - user: {{ pillar['login_user'] }}

  supervisor-init-script:
    file.managed:
      - user: {{ pillar['login_user'] }}

  /etc/supervisor/conf.d/inform.conf:
    file.managed:
      - context:
          purge: true

  tmux-powerline-theme:
    file.managed:
      - context:
          gunicorn: true
          celeryd: true
