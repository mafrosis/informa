base:
  '*':
    - common
    - salt-backports
    - inform

  'env:prod':
    - match: grain
    - raspi-config
    - hostname
    - locale

  'env:dev':
    - match: grain
    - dev-user
    - dev-build
