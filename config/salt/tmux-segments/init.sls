# install tmux segments for gunicorn & celeryd state
{% for app in ('gunicorn', 'celeryd') %}
tmux-{{ app }}-segment:
  file.managed:
    - name: /home/{{ pillar['login_user'] }}/tmux-powerline/segments/{{ app }}.sh
    - source: salt://tmux/pid-segment.tmpl.sh
    - template: jinja
    - user: {{ pillar['login_user'] }}
    - context:
        component_name: {{ app }}
    - require:
      - cmd: dotfiles-install-tmux
      - git: tmux-powerline-install
{% endfor %}
