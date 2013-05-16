from lib.plugin import InformBasePlugin

from datetime import timedelta

import requests
import time

from bs4 import BeautifulSoup


BASE_URL = "http://thepiratebay.sx"
SEARCH_URL = "{0}/search/f1/0/99/208".format(BASE_URL)
UA = "curl/7.24.0 (x86_64-apple-darwin12.0) libcurl/7.24.0 OpenSSL/0.9.8r zlib/1.2.5"
MAX_TORRENTS = 10


class InformPlugin(InformBasePlugin):
    run_every = timedelta(minutes=60)

    def process(self):
        # load last known torrent id
        prev_tid = self.load("f1_torrents_last_known_tid", default=0)
        max_tid = prev_tid

        data = []

        try:
            resp = requests.get(SEARCH_URL, headers={'User-Agent': UA})
            if resp.status_code != 200:
                raise Exception("Non 200 return from search page")

            # extract all torrent links
            soup = BeautifulSoup(resp.text)
            torrents = soup.find_all('a', attrs={'class': 'detLink'})

            for trnt in torrents:
                tid = int(trnt['href'][9:trnt['href'].rfind("/")])

                # only care about new torrents
                if tid > prev_tid:
                    # load the torrent detail page
                    resp = requests.get("{0}{1}".format(BASE_URL, trnt['href']))
                    if resp.status_code != 200:
                        raise Exception("Non 200 return from detail page")

                    # parse the torrent meta data
                    soup = BeautifulSoup(resp.text)

                    details1 = soup.find(
                        'div', attrs={'id': 'details'}
                    ).find(
                        'dl', attrs={'class': 'col1'}
                    ).text.strip().replace(u'\xa0', u' ')

                    # verify MUST be engrish
                    if 'English' not in details1:
                        continue

                    details2 = soup.find(
                        'div', attrs={'id': 'details'}
                    ).find(
                        'dl', attrs={'class': 'col2'}
                    ).text.strip().replace(u'\xa0', u' ')

                    # sometimes col2 is empty and picture is shown
                    if details2.strip() == '':
                        details2 = details1[details1.find("Uploaded"):]

                    # crop the details1 down
                    details1 = details1[0:details1.find("Spoken language")]

                    # set the end of details1 to Tag or len()
                    tagpos = details1.find("Tag")
                    if tagpos == -1:
                        tagpos = len(details1)

                    # set the end of deails1 to Texted lang or Comments
                    compos = details2.find("Texted language")
                    if compos == -1:
                        compos = details2.find("Comments")

                    # merge the two details blocks into a single piece of meta
                    meta = "{0}\n{1}".format(
                        details1[details1.find("Size"):tagpos],
                        details2[0:compos]
                    ).strip().replace("   ", " ").replace("  ", " ")

                    # grab one of the download links, preferring magnet
                    a = soup.find('div', attrs={'class': 'download'}).findChildren("a")[0]
                    if a['href'].startswith('magnet'):
                        url = a['href']
                    else:
                        url = "http:{0}".format(a['href'])

                    data.append({
                        'name': trnt.text,
                        'tid': tid,
                        'meta': meta.replace("\n", " "),
                        'url': url,
                    })
                    if tid > max_tid:
                        max_tid = tid

                    time.sleep(3)

                    if len(data) == MAX_TORRENTS:
                        break

            # store most recent torrent id
            self.store("f1_torrents_last_known_tid", max_tid)

        except Exception as e:
            print "Failed loading F1 torrents {0}".format(e)
            return {}

        self.store(__name__, data)
        return data
