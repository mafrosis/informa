base:
  '*':
    - common
    - informa

  'env:prod':
    - match: grain
    - hostname
    - locale

  'env:dev':
    - match: grain
    - dev-user
    - dev-build
