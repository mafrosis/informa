base:
  'env:dev':
    - match: grain
    - dev_vars
  'env:prod':
    - match: grain
    - prod_vars
