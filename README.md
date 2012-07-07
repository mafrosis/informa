Inform
======

A python project for pulling information from the web (and elsewhere) and storing it locally in memcache. This is then offered as structured JSON via a simple HTTP webservice. 

This was built to pull data from various website APIs and provide it for display on an LCD screen on my wall. The scheduled tasks provided by celery are great for consuming web APIs in the background, and memcache storage is perfect for storage of this transient data. A small flask app sits on top of the that to provide access to the memcache store.


Dependencies
============

As ever, standing on the shoulders of giants:

	aptitude install nginx rabbitmq-server virtualenvwrapper supervisor memcached


Installation
============

	mkdir -p /srv/www
	cd /srv/www
	git clone git://github.com/mafrosis/inform.git

Salt
----

[Salt](http://saltstack.org) is a great configuration management tool. If you have the time, run through their [install](http://docs.saltstack.org/en/latest/topics/installation/index.html) and set your machine as both master and a minion.

	cd config
	salt 'localhost' state.highstate 

Manual
------

	mkvirtualenv inform
	pip install -r config/requirements
	sudo ln -s /srv/www/inform/config/supervisor.conf /etc/supervisor/conf.d/
	sudo service supervisor stop
	sudo service supervisor start

Nginx
-----

Written for version 1.2.1.

If you already have Nginx setup on your server, you'll want to have a look at **config/nginx.conf** and merge into your existing config file. Otherwise the following should be sufficient(note: if you want to serve externally you will need to configure that yourself):

	sudo ln -s /srv/www/inform/config/nginx.conf /etc/nginx/sites-available/inform.conf
	sudo ln -s /etc/nginx/sites-available/inform.conf /etc/nginx/sites-enabled/
	sudo service nginx restart


Usage
=====

After install, the service should be running quietly in the background. Check with **supervisorctl** that gunicorn and celery have both started correctly:

	sudo supervisorctl status

Assuming both services are up, query the flask app to see what's been added to the memcache store:

	curl localhost:8004/get


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
