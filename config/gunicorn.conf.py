#################################################
# Gunicorn config for informa
#################################################

bind = '127.0.0.1:8003'

# configure number of gunicorn workers
import multiprocessing
workers = multiprocessing.cpu_count() * 2 + 1

# dont daemonize; running inside docker
daemon = False
timeout = 30
pidfile = '/tmp/gunicorn.pid'

# error log to STDERR
errorlog = '-'
loglevel = 'info'
