#!/usr/bin/env python3

import csv
import datetime
import html
import json
import os
import subprocess
import urllib.request

start = datetime.datetime.now()

SERIES = ['motogp', 'moto2', 'moto3']
MAX_SEASONS = 20

IGNORE_KEYS = {'type', 'code', 'uuid', 'picture',
               'race', 'winner', 'venue',
               'hasResults', 'preciseStartTime'}
TIME_KEYS = {'time', 'timeToLead', 'timeToNext'}

CONVERTERS = {
    'date': datetime.datetime.fromtimestamp,
    'endTime': datetime.datetime.fromtimestamp,
    # 'endTimeUtc': datetime.datetime.fromtimestamp,
    'startTime': datetime.datetime.fromtimestamp,
    # 'startTimeUtc': datetime.datetime.fromtimestamp,
}
CACHE_DIR = 'cache'

API_BASE = 'https://mssproxy.motorsportstats.com/web/3.0.0/'
SEASONS_URL =   API_BASE + 'series/%s/seasons'
RACES_URL =     API_BASE + 'seasons/%s/races'
SESSIONS_URL =  API_BASE + 'events/%s/sessions'
CLASS_URL =     API_BASE + 'sessions/%s/classification'

stats = {
    'series': 0,
    'seasons': 0,
    'events': 0,
    'sessions': 0,
    'pages scraped': 0,
    'classifications': 0,
}

fieldnames = [
    'season_name', 'year', 'event_name', 'date', 'session_name',
    'sessionNumber', 'hasFacts', 'isTimetable', 'startTime', 'startTimeUtc',
    'endTime', 'endTimeUtc', 'finishPosition', 'carNumber', 'classifiedStatus',
    'drivers_name', 'nationality_name', 'seriesClass', 'team_name', 'laps',
    'time', 'timeHuman', 'avgLapSpeed', 'gap_timeToLead',
    'gap_timeToLeadHuman', 'gap_timeToNext', 'gap_timeToNextHuman',
    'gap_lapsToLead', 'gap_lapsToNext', 'bestLap_lap', 'bestLap_time',
    'bestLap_timeHuman', 'bestLap_fastest', 'bestLap_speed',
    'seriesClass_name', 'nationality',
]


class Opener(urllib.request.URLopener):

    def get(self, url):
        stats['pages scraped'] += 1
        filename = os.path.join(CACHE_DIR, url.lstrip('https://'))
        if not os.path.exists(filename):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            print('getting', url)
            self.retrieve(url, filename)
        with open(filename) as fp:
            return json.load(fp)

    @property
    def version(self):
        return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36'


def flatten(dst, src, prefix=''):
    for key, value in src.items():
        if key in IGNORE_KEYS:
            continue
        if isinstance(value, list):
            assert len(value) == 1
            value = value[0]
        if isinstance(value, dict):
            flatten(dst, value, prefix + key + '_')
        else:
            if value and key in CONVERTERS:
                value = CONVERTERS[key](value)
            dst[prefix + key] = value
            if key in TIME_KEYS:
                key += 'Human'
                dst[prefix + key] = timestr(value)


def timestr(time):
    if time is None:
        return None
    s = time / 1000
    ms = time % 1000
    m = s / 60
    s %= 60
    assert m < 60
    return '%d.%02d.%03d' % (m, s, ms)


def getseries(series, writers=[]):
    opener = Opener()
    stats['series'] += 1
    seasons_url = SEASONS_URL % series
    for season in opener.get(seasons_url)[:MAX_SEASONS]:
        stats['seasons'] += 1
        for race in opener.get(RACES_URL % season['season']['uuid']):
            stats['events'] += 1
            for session in opener.get(SESSIONS_URL % race['event']['uuid']):
                if not session['hasResults']:
                    continue
                stats['sessions'] += 1
                classifications = opener.get(CLASS_URL % session['session']['uuid'])
                for classification in classifications['details']:
                    row = {}
                    flatten(row, season)
                    flatten(row, race)
                    flatten(row, session)
                    flatten(row, classification)
                    for writer in writers:
                        writer.writerow(row)
                    stats['classifications'] += 1


def sizestr(n):
    SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while n >= 1000:
        i += 1
        n /= 1000
    return '{0:.02f} {1}'.format(n, SIZE_UNITS[i])


if __name__ == '__main__':
    files = []
    combined_csv = 'allseries.csv'
    with open(combined_csv, 'w') as fp:
        combined = csv.DictWriter(fp, fieldnames)
        combined.writeheader()
        for series in SERIES:
            filename = series + '.csv'
            files.append(filename)
            with open(filename, 'w') as fp:
                writer = csv.DictWriter(fp, fieldnames)
                writer.writeheader()
                getseries(series, [writer, combined])
    files.append(combined_csv)
    # cache_tar = CACHE_DIR + '.tar.gz'
    # subprocess.call(['tar', 'czf', cache_tar, CACHE_DIR])
    # files.append(cache_tar)
    # files.append(os.path.basename(__file__))
    now = datetime.datetime.now()
    with open('index.html', 'w') as fp:
        fp.write('<html><head><title>moto data</title></head><body>')
        fp.write('<h1>moto data</h1>')
        fp.write('<p>Last updated: %s</p>' % now)
        fp.write('<h2>Downloads</h2>')
        fp.write('<ul>')
        for filename in files:
            fp.write('<li><a href="{0}">{0}</a> ({1})</li>'.format(
                filename, sizestr(os.path.getsize(filename))))
        fp.write('</ul>')
        fp.write('<h2>Stats</h2>')
        fp.write('<ul>')
        for stat in stats.items():
            fp.write('<li>{1} {0}</li>'.format(*stat))
        fp.write('</ul>')
        # fp.write('<h2>Code</h2>')
        # with open(__file__) as gp:
        #     fp.write('<pre>%s</pre>' % html.escape(gp.read()))
        fp.write('<p>Generated in %s</p>' % (now-start))
        fp.write('</body></html>')
