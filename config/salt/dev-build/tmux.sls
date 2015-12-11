#
# Extra tmux configuration for dev-builds
#

# create tmux-powerline theme, including custom defined segments
tmux-powerline-theme:
  file.managed:
    - name: /home/vagrant/tmux-powerline/themes/ogreserver.sh
    - source: salt://dev-build/tmux-powerline-theme.conf
    - user: vagrant
    - group: vagrant
    - require:
      - cmd: bootstrap-dotfiles

tmux-powerlinerc-patch:
  file.replace:
    - name: /home/vagrant/.tmux-powerlinerc
    - pattern: ^export TMUX_POWERLINE_THEME="default"
    - repl: export TMUX_POWERLINE_THEME="ogreserver"
    - append_if_not_found: true
    - backup: false

# install tmux segments for gunicorn & celeryd state
{% for service in ('gunicorn', 'celeryd') %}
tmux-{{ service }}-segment:
  file.managed:
    - name: /home/vagrant/tmux-powerline/segments/{{ service }}.sh
    - source: salt://dev-build/tmux-pid-segment.sh
    - template: jinja
    - user: vagrant
    - mode: 755
    - context:
        component_name: {{ service }}
        app_name: ogreserver
    - require:
      - cmd: bootstrap-dotfiles
{% endfor %}

# add tmux init commands to setup environment
tmux-ogre-init-conf:
  file.managed:
    - name: /home/vagrant/.tmux-ogre-init.conf
    - source: salt://dev-build/tmux-ogre-init.conf
    - user: vagrant
    - group: vagrant

tmux-ogre-init-conf-patch:
  file.append:
    - name: /home/vagrant/.tmux.conf
    - text: "\n# AUTOMATICALLY ADDED TMUX SALT CONFIG\nsource-file ~/.tmux-ogre-init.conf"
    - require:
      - cmd: bootstrap-dotfiles
