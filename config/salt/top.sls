base:
  '*':
    - common
    - inform

  'env:dev':
    - match: grain
    - dev-user
    - dev-build
