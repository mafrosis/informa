Inform
======

A python project for pulling information from the web (and elsewhere) and storing it locally in memcache. This is then offered as structured JSON via a simple HTTP webservice. 

This was built to pull data from various website APIs and provide it for display on an LCD screen on my wall. The scheduled tasks provided by celery are great for consuming web APIs in the background, and memcache storage is perfect for storage of this transient data. A small flask app sits on top of the that to provide access to the memcache store. Data can also be persisted to Redis if necessary.


Dependencies
============

  - Docker
  - Docker Compose


Usage
=====

Docker Compose will pull/build containers at first run:

    docker-compose up

Then view the current state of all data via HTTP:

	  curl <informa-host>:8003/get

Manually invoke a plugin with `docker-compose exec`:

    docker-compose exec flask flask load melmetro

(The first `flask` is the container name, the second is the `flask` binary).


Production
==========

Build for production on raspberry Pi with the following command:

    BUILD_TAG=prod docker-compose -f docker-compose.yml -f docker-compose.prod.yml build flask


Plugins
=======

A plugin exists to pull data into the store. Each one will run periodically as a celery task.

Plugins will likely have their own configuration and requirements. This is written directly into the plugin header for simplicity - review and configure your plugins to get your setup right.

The best way to learn how to write a plugin is by reading and copying **plugins/tramtracker.py**. This is a good example of a really simple plugin, which pulls data from a webservice API over HTTP.

Required code for a plugin:

	from lib.plugin import InformBasePlugin

	class InformPlugin(InformBasePlugin):

	  def process(self):
		  # get some data from the internets
		  data = {}
		  self.store(__name__, data)

By default a plugin will run the process() method every 30 minutes. You can change this by adding the following class property to your plugin - for example to run every 5 minutes:

	run_every = timedelta(minutes=5)

The following plugins bundled with the application. Any extra requirements are listed:

  * **tramtracker** - load realtime Melbourne tram times from tramtracker.com.au. The default stop ID is near my house.
  * **weather** - pull/parse data from UK MetOffice, AU Bureau of Meteorology and Wunderground. Pull both latest observations and forecasts for Melbourne, AU and Bristol, UK.
  * **rtorrent** - load data from rtorrent via XMLRPC on the SCGI interface. Displays torrent names and percent complete from a custom view called 'inform'. (Requires **rtorrent**).
  * **livescore** - use Selenium to parse javascript and extract current match stats from football website livescore.in. Setup for Liverpool FC by default. (Requires **selenium**, **firefox** & **xvfb**).


Troubleshooting
===============

First check with **supervisorctl** that gunicorn and celery have both started correctly:

	sudo supervisorctl status

If something failed here, check the supervisor logs to see what went wrong:

	tail -20 /var/log/mafro/inform/supervisor.log

As objects are written to memcache they are also logged in this file. This should be apparent if things are working..

You can also check the contents of the memcache store on the command line. Enter the virtualenv and use the manage command:

	cd /srv/www/inform; workon inform
	./manage.py get
