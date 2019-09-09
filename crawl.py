#!/usr/bin/env python3

import csv
import json
import os
import sys
import urllib.request

from bs4 import BeautifulSoup

API_BASE = 'https://mssproxy.motorsportstats.com/web/3.0.0/'
WEB_BASE = 'https://results.motorsportstats.com/'

SEASONS_URL =   API_BASE + 'series/%s/seasons'
RACES_URL =     API_BASE + 'seasons/%s/races'
CONST_URL =     API_BASE + 'seasons/%s/standings/constructors'
SESSIONS_URL =  API_BASE + 'events/%s/sessions'
CLASS_URL =     API_BASE + 'sessions/%s/classification'
TEST_URL =      WEB_BASE + 'results/%s'

SERIESES = ['motogp']

numgets = 0

APP_PREFIX = 'window.App='

class Opener(urllib.request.URLopener):

    @property
    def version(self):
        return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36'

opener = Opener()

def get(url):
    global numgets
    numgets += 1
    filename = url.lstrip('https://')
    if not os.path.exists(filename):
        dirname, basename = os.path.split(filename)
        try:
            os.makedirs(dirname)
        except:
            pass
        print('getting', url)
        opener.retrieve(url, filename)
    with open(filename) as fp:
        if url.startswith(WEB_BASE):
            soup = BeautifulSoup(fp)
            for script in soup.find_all('script'):
                if script.text and script.text.startswith(APP_PREFIX):
                    return json.loads(script.text.lstrip(APP_PREFIX))
        else:
            return json.load(fp)

fieldnames = {}

IGNORE_KEYS = {'type', 'code', 'uuid', 'picture', 'hasResults'}

def flatten(src, dst, prefix=''):
    for key, value in src.items():
        if key in IGNORE_KEYS:
            continue
        if isinstance(value, list):
            assert len(value) == 1
            value = value[0]
        if isinstance(value, dict):
            flatten(value, dst, prefix + key + '.')
        else:
            dst[prefix + key] = value
            fieldnames[prefix + key] = 1

rows = []
for series in SERIESES:
    seasons_url = SEASONS_URL % series
    for season in get(seasons_url)[:2]:
        season_id = season['season']['uuid']
        races_url = RACES_URL % season_id
        races = get(races_url)
        for race in races:
            del race['race']
            del race['winner']
            del race['venue']
            race_id = race['event']['uuid']
            app = get(TEST_URL % race_id)
            for session in app['state']['event']['sessions']['list']['data']:
                if not session['hasResults']:
                    continue
                session_id = session['session']['uuid']
                try:
                    classifications = get(CLASS_URL % session_id)
                    assert(session['hasResults'])
                    for classification in classifications['details']:
                        row = {}
                        flatten(season, row)
                        flatten(race, row)
                        flatten(session, row)
                        flatten(classification, row)
                        rows.append(row)
                except urllib.error.HTTPError:
                    if session['hasResults']:
                        print(session)
                        raise
with open('data.csv', 'w') as fp:
    writer = csv.DictWriter(fp, fieldnames.keys())
    writer.writeheader()
    writer.writerows(rows)
print(fieldnames.keys())
print(numgets)
