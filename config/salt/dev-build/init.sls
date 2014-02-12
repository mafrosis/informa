include:
  - tmux-segments

extend:
  gunicorn-config:
    file.managed:
      - context:
          bind_hostname: "0.0.0.0"
          gunicorn_port: {{ pillar['gunicorn_port'] }}
          timeout: 300
          loglevel: info

  #supervisor-config:
  #  file.managed:
  #    - context:
  #        socket_mode: 0777

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
