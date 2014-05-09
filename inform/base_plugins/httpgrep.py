from . import InformBasePlugin

from datetime import timedelta

import requests


class HttpGrepPlugin(InformBasePlugin):
    run_every = timedelta(minutes=10)
    enabled = False

    url = 'www.google.com'
    terms = ['google']

    def process(self):
        try:
            r = requests.get(self.url)
        except:
            print "Failed loading from {}".format(self.url)
            return {}

        data = {}

        try:
            for t in self.terms:
                if t in r.text:
                    data[t] = True
                else:
                    data[t] = False

        except Exception as e:
            print "Error grepping HTML: {}".format(e)
            return {}

        self.store(data)
        return data
