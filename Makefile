.PHONY: celerybeat celery flask gunicorn

celerybeat:
	rm -f /run/celerybeat.pid
	C_FORCE_ROOT=1 celery beat -A entrypoint.celery --pidfile=/run/celerybeat.pid

celery:
	C_FORCE_ROOT=1 celery worker -A entrypoint.celery --workdir=/srv/app --purge

flask:
	flask run --host 0.0.0.0 --port 8003 --reload --no-debugger

gunicorn:
	gunicorn entrypoint:app -c /srv/app/config/gunicorn.conf.py
