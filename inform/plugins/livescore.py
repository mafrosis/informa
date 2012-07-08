from lib.plugin import InformBasePlugin

from selenium import webdriver
from datetime import datetime, timedelta

import os
import time
import json

os.environ['DISPLAY'] = ":99"

PREM_LISTING_URL = "http://www.livescore.in/iframe/sport.php?sport=soccer&category=198"
MATCH_URL = "http://www.livescore.in/match/%s/#match-summary"
TEAM = "Liverpool"


class InformPlugin(InformBasePlugin):
    run_every = timedelta(days=1)

    def process(self):
        driver = webdriver.Firefox()

        try:
            # load the iframe in selenium
            driver.get(PREM_LISTING_URL)
            time.sleep(5)

            # get the EPL table
            epl = driver.find_element_by_class_name("soccer").find_element_by_tag_name("tbody")

            data = []

            # extract all match details
            for match in epl.find_elements_by_tag_name("tr"):
                d = datetime.strptime(match.find_element_by_class_name("time").text.strip(), "%d.%m. %H:%M")
                match_date = datetime(datetime.now().year, d.month, d.day, d.hour, d.minute)

                home_team = match.find_element_by_class_name("team-home").find_element_by_tag_name("span").text.strip()
                away_team = match.find_element_by_class_name("team-away").find_element_by_tag_name("span").text.strip()
                timer = match.find_element_by_class_name("timer").find_element_by_tag_name("span").text.strip()
                score = match.find_element_by_class_name("score").text.strip()

                # process match info for LFC
                if home_team == TEAM or away_team == TEAM:
                    scorers = self.lfc(match.get_attribute('id')[4:])

                    data.append({
                        'date': match_date.isoformat(),
                        'time': timer,
                        'home': home_team,
                        'away': away_team,
                        'score': score,
                        'scorers': scorers,
                    })

            self.store(__name__, data)
            return data

        finally:
            driver.close()


    def lfc(self, match_id):
        driver = webdriver.Firefox()

        try:
            # load the match details URL in selenium
            driver.get(MATCH_URL % match_id)
            time.sleep(1)

            # get the match summary
            match = driver.find_element_by_id("parts").find_element_by_tag_name("tbody")

            scorers = []

            # extract HOME team goal events
            for item in match.find_elements_by_class_name("fl"):
                self.parse_goal(item, scorers, 'H')

            # extract AWAY team goal events
            for item in match.find_elements_by_class_name("fr"):
                self.parse_goal(item, scorers, 'A')

            # sort all goals by time
            return sorted(scorers, key=lambda goal: goal['time'])

        finally:
            driver.close()


    def parse_goal(item, scorers, t):
        scorer = "??????"
        time = "??"
        own_goal = False

        try:
            # if there's a soccer-ball element, we have a goal..
            item.find_element_by_class_name("soccer-ball")
        except:
            try:
                # if there's a soccer-ball-own element, we have an own goal..
                item.find_element_by_class_name("soccer-ball-own")
                own_goal = True
            except:
                # otherwise ignore
                return

        try:
            # try to extract clean data
            parts = item.text.split("\n")
            if own_goal == False:
                scorer = parts[1].strip()
            else:
                scorer = parts[1].strip()[:-11] + " OG"

            time = int(parts[0].strip()[:-1])
        except:
            # else display defaults
            pass

        scorers.append({
            'time': time,
            'name': scorer,
            'type': t,
        })
