base:
  '*':
    - common
    - salt-backports
    - inform

  'env:dev':
    - match: grain
    - dev-user
    - dev-build
