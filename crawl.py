#!/usr/bin/env python3
import csv
import datetime
import html
import json
import os
import subprocess
import sys
import urllib.request

from bs4 import BeautifulSoup

start = datetime.datetime.now()

SERIES = ['motogp', 'moto2', 'moto3']
MAX_SEASONS = 20
IGNORE_KEYS = {'type', 'code', 'uuid', 'picture', 'hasResults', 'preciseStartTime'}
# DATE_KEYS = {'startTimeUtc', 'endTimeUtc'}
DATE_KEYS = {'date', 'startTime', 'endTime'}
CACHE_DIR = 'cache'

API_BASE = 'https://mssproxy.motorsportstats.com/web/3.0.0/'
SEASONS_URL =   API_BASE + 'series/%s/seasons'
RACES_URL =     API_BASE + 'seasons/%s/races'
CONST_URL =     API_BASE + 'seasons/%s/standings/constructors'
SESSIONS_URL =  API_BASE + 'events/%s/sessions'
CLASS_URL =     API_BASE + 'sessions/%s/classification'

stats = {
    'series': 0,
    'seasons': 0,
    'events': 0,
    'sessions': 0,
    'pages scraped': 0,
    'rows of data': 0,
}


def human_size(n):
    SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while n > 1000:
        i += 1
        n /= 1000
    return '{0:.02f} {1}'.format(n, SIZE_UNITS[i])


class Opener(urllib.request.URLopener):

    def get(self, url):
        stats['pages scraped'] += 1
        filename = os.path.join(CACHE_DIR, url.lstrip('https://'))
        if not os.path.exists(filename):
            dirname, basename = os.path.split(filename)
            try:
                os.makedirs(dirname)
            except:
                pass
            print('getting', url)
            self.retrieve(url, filename)
        with open(filename) as fp:
            return json.load(fp)

    @property
    def version(self):
        return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36'


def flatten(src, dst, prefix=''):
    for key, value in src.items():
        if key in IGNORE_KEYS:
            continue
        if isinstance(value, list):
            assert len(value) == 1
            value = value[0]
        if isinstance(value, dict):
            flatten(value, dst, prefix + key + '_')
        else:
            if value and key in DATE_KEYS:
                value = datetime.datetime.fromtimestamp(value)
            dst[prefix + key] = value
            fieldnames[prefix + key] = 1

def getseries(series):
    opener = Opener()
    rows = []
    filename = series + '.csv'
    stats['series'] += 1
    seasons_url = SEASONS_URL % series
    for season in opener.get(seasons_url)[:MAX_SEASONS]:
        stats['seasons'] += 1
        season_id = season['season']['uuid']
        races_url = RACES_URL % season_id
        races = opener.get(races_url)
        for race in races:
            stats['events'] += 1
            del race['race']
            del race['winner']
            del race['venue']
            race_id = race['event']['uuid']
            for session in opener.get(SESSIONS_URL % race_id):
                if not session['hasResults']:
                    continue
                stats['sessions'] += 1
                session_id = session['session']['uuid']
                classifications = opener.get(CLASS_URL % session_id)
                for classification in classifications['details']:
                    row = {}
                    flatten(season, row)
                    flatten(race, row)
                    flatten(session, row)
                    flatten(classification, row)
                    rows.append(row)
    with open(filename, 'w') as fp:
        writer = csv.DictWriter(fp, fieldnames.keys())
        writer.writeheader()
        writer.writerows(rows)
        stats['rows of data'] += len(rows)
    print(fieldnames.keys())
    return filename


def combine_csv(srcs, dst):
    with open(dst, 'w') as fp:
        writer = csv.DictWriter(fp, fieldnames)
        writer.writeheader()
        for src in srcs:
            with open(src) as fp:
                for row in csv.DictReader(fp):
                    writer.writerow(row)


if __name__ == '__main__':
    fieldnames = {}
    files = []
    for series in SERIES:
        files.append(getseries(series))
    combined_csv = 'all.csv'
    combine_csv(files, combined_csv)
    files.append(combined_csv)
    cache_tar = CACHE_DIR + '.tar.gz'
    subprocess.call(['tar', 'czf', cache_tar, CACHE_DIR])
    files.append(cache_tar)
    files.append(os.path.basename(__file__))
    now = datetime.datetime.now()
    with open('index.html', 'w') as fp:
        fp.write('<html><head><title>moto data</title></head><body>')
        fp.write('<h1>moto data</h1>')
        fp.write('<p>Last updated: %s</p>' % now)
        fp.write('<h2>Downloads</h2>')
        fp.write('<ul>')
        for filename in files:
            fp.write('<li><a href="{0}">{0}</a> ({1})</li>'.format(
                filename, human_size(os.path.getsize(filename))))
        fp.write('</ul>')
        fp.write('<h2>Stats</h2>')
        fp.write('<ul>')
        for stat in stats.items():
            fp.write('<li>{1} {0}</li>'.format(*stat))
        fp.write('</ul>')
        fp.write('<p>Generated in %s</p>' % (now-start))
        fp.write('</body></html>')
