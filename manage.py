#! /usr/bin/env python

from __future__ import absolute_import
from flask.ext.script import Manager

from inform import app, modules, views

manager = Manager(app)

@manager.command
def get():
    print views.get().data

@manager.command
def load(name):
    if name in modules.keys():
        modules[name].process()

if __name__ == "__main__":
    manager.run()
