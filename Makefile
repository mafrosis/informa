celerybeat:
	rm -f /run/celerybeat.pid
	C_FORCE_ROOT=1 celery beat -A manage.celery --pidfile=/run/celerybeat.pid

celery:
	C_FORCE_ROOT=1 celery worker -A manage.celery --workdir=/srv/app --purge

flask:
	./manage.py runserver --host 0.0.0.0 --port 8003 --debug

gunicorn:
	gunicorn manage:app -c /srv/app/config/gunicorn.conf.py
