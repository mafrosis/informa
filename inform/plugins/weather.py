from lib.plugin import InformBasePlugin

import requests
import json

from datetime import datetime

from BeautifulSoup import BeautifulSoup

from inform.utils import soupselect
soupselect.monkeypatch()


MET_KEY = "199dcfbb-ae30-49b9-86d5-670a67cd867b"
BRISTOL_STN = "3628"
WUND_KEY = "079951779a915985"

MET_CODES = {
    '0': "Clear sky",
    '1': "Sunny",
    '2': "Partly cloudy (night)",
    '3': "Sunny intervals",
    '4': "Dust",
    '5': "Mist",
    '6': "Fog",
    '7': "Medium-level cloud",
    '8': "Low-level cloud",
    '9': "Light rain shower (night)",
    '10': "Light rain shower (day)",
    '11': "Drizzle",
    '12': "Light rain",
    '13': "Heavy rain shower (night)",
    '14': "Heavy rain shower (day)",
    '15': "Heavy rain",
    '16': "Sleet shower (night)",
    '17': "Sleet shower (day)",
    '18': "Sleet",
    '19': "Hail shower (night)",
    '20': "Hail shower (day)",
    '21': "Hail",
    '22': "Light snow shower (night)",
    '23': "Light snow shower (day)",
    '24': "Light snow",
    '25': "Heavy snow shower (night)",
    '26': "Heavy snow shower (day)",
    '27': "Heavy snow",
    '28': "Thundery shower (night)",
    '29': "Thundery shower (day)",
    '30': "Thunder storm",
    '31': "Tropical storm",
    '33': "Haze",
}


class InformPlugin(InformBasePlugin):

    def process(self):
        data = {
            'mel-latest': self.boml(),
            'mel-forecast': self.bomf(),
            'bri-latest': self.metl(),
            'bri-forecast': self.metf(),
            'mel-astro': self.astro(),
        }
        self.store(__name__, data)
        return data


    def boml(self):
        # latest observation from Melb central
        r = requests.get("http://www.bom.gov.au/fwo/IDV60901/IDV60901.94868.json")
        data = json.loads(r.text)
        return {
            'location': data['observations']['header'][0]['name'],
            'lat': data['observations']['data'][0]['lat'],
            'long': data['observations']['data'][0]['lon'],
            'temp': data['observations']['data'][0]['air_temp'],
            'feels': data['observations']['data'][0]['apparent_t'],
        }


    def bomf(self):
        # forecast for Melbourne
        r = requests.get("http://www.bom.gov.au/vic/forecasts/melbourne.shtml")
        
        # parse tomorrow's weather using soup
        soup = BeautifulSoup(r.text)
        tm = soup.find('div', attrs={'class': 'day'})

        # temperature
        mn = tm.find('em', attrs={'class': 'min'}).text
        mx = tm.find('em', attrs={'class': 'max'}).text
        temp = (int(mx) + int(mn)) / 2

        # date
        d = datetime.strptime(tm.find('h2').text+" %s" % datetime.now().year, "%A %d %B %Y")

        # weather type
        t = tm.find('img').attrs[0][1][22:-4]

        return {
            'date': d.isoformat(),
            'temp': temp,
            'type': t,
        }


    def metl(self):
        # observations from Bristol Filton
        r = requests.get("http://partner.metoffice.gov.uk/public/val/wxobs/all/json/%s?res=daily&key=%s" % (BRISTOL_STN, MET_KEY))
        data = json.loads(r.text)
        d = datetime.strptime(data['SiteRep']['DV']['Location']['Period'][0]['@val'], "%Y-%m-%dZ")
        return {
            'date': d.isoformat(),
            'location': data['SiteRep']['DV']['Location']['@name'],
            'lat': data['SiteRep']['DV']['Location']['@lat'],
            'long': data['SiteRep']['DV']['Location']['@lon'],
            'temp': data['SiteRep']['DV']['Location']['Period'][0]['Rep'][0]['@T'],
            'type': MET_CODES[data['SiteRep']['DV']['Location']['Period'][0]['Rep'][0]['@W']],
        }


    def metf(self):
        # forecast from Bristol Filton
        r = requests.get("http://partner.metoffice.gov.uk/public/val/wxfcs/all/json/%s?res=daily&key=%s" % (BRISTOL_STN, MET_KEY))
        data = json.loads(r.text)
        d = datetime.strptime(data['SiteRep']['DV']['Location']['Period'][0]['@val'], "%Y-%m-%dZ")
        return {
            'date': d.isoformat(),
            'location': data['SiteRep']['DV']['Location']['@name'],
            'lat': data['SiteRep']['DV']['Location']['@lat'],
            'long': data['SiteRep']['DV']['Location']['@lon'],
            'temp': data['SiteRep']['DV']['Location']['Period'][0]['Rep'][0]['@Dm'],
            'feels': data['SiteRep']['DV']['Location']['Period'][0]['Rep'][0]['@FDm'],
            'type': MET_CODES[data['SiteRep']['DV']['Location']['Period'][0]['Rep'][0]['@W']],
        }


    def astro(self):
        r = requests.get("http://api.wunderground.com/api/%s/astronomy/q/Australia/Melbourne.json" % WUND_KEY)
        data = json.loads(r.text)

        # try parsing sunrise/sunset datetimes
        try:
            sunrise = datetime(datetime.now().year, datetime.now().month, datetime.now().day, int(data['moon_phase']['sunrise']['hour']), int(data['moon_phase']['sunrise']['minute']))
            sunset = datetime(datetime.now().year, datetime.now().month, datetime.now().day, int(data['moon_phase']['sunset']['hour']), int(data['moon_phase']['sunset']['minute']))
        except:
            pass

        # get the full% of the moon
        return {
            'moon': data['moon_phase']['percentIlluminated'],
            'sunrise': sunrise.isoformat(),
            'sunset': sunset.isoformat(),
        }
