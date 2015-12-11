# this file provides defaults for dev_vars.sls
app_user: vagrant
app_repo_rev: master
login_user: vagrant

gunicorn_host: localhost
gunicorn_port: 8003

hostname: informa
timezone: Australia/Melbourne
locale: en_AU

rabbitmq_host: localhost
rabbitmq_vhost: dev
rabbitmq_user: dev
rabbitmq_pass: dev

# get dotfiles from github
github_username: mafrosis

# install zsh and set as default login shell
shell: zsh

# install extras from apt and install dotfiles
extras:
  - vim
  - zsh
  - git
  - tmux

# install extras from pip
pip:
  - pyflakes
  - virtualenvwrapper

# set backports to AU in bit.ly/19Nso9M
deb_mirror_prefix: ftp.au
