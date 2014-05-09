app_name: inform
app_user: vagrant
app_repo: mafrosis/inform
login_user: vagrant

flask_debug: true
secret_key: ssh_its_a_secret
zapier_email_webhook_id: ""

gunicorn_host: localhost
gunicorn_port: 8003

hostname: inform
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

# set the path to your github private key, from the salt file_roots directory
github_key_path: github.dev.pky
