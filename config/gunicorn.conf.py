import os

def numCPUs():
	if not hasattr(os, "sysconf"):
		raise RuntimeError("No sysconf detected.")
	return os.sysconf("SC_NPROCESSORS_ONLN")

bind = '127.0.0.1:8004'
#workers = numCPUs() * 2 + 1
backlog = 2048
worker_class = "sync"
debug = True
#daemon = True
proc_name = 'inform'
pidfile = '/tmp/gunicorn-inform.pid'
logfile = '/var/log/mafro/inform/gunicorn.log'
#loglevel = 'debug'

