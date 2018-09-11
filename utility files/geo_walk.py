import os
import sqlite3
import re
import requests
import pickle
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

__author__ = 'kongaloosh'

path = 'data/'

url_bit = "kongaloosh.com/e/"

list_of_files = {}
conn = sqlite3.connect('kongaloosh.db')
g = conn.cursor()


def get_bare_file(filename):
    """ for a given entry, finds all of the info we want to display """
    """ for a given entry, finds all of the info we want to display """
    f = open(filename, 'r')
    str = f.read()
    str = str.decode('utf-8')
    e = {}
    try: e['title'] = re.search('(?<=title:)(.)*', str).group()
    except: pass
    try: e['slug'] = re.search('(?<=slug:)(.)*', str).group()
    except: pass
    try: e['summary'] = re.search('(?<=summary:)(.)*', str).group()
    except: pass
    try:
        e['content'] =re.search('(?<=content:)((?!category:)(?!published:)(.)|(\n))*', str).group()
        if e['content'] == None:
            e['content'] = re.search('(?<=content:)((.)|(\n))*$', str).group()
    except:
        pass
    try:
        e['published'] = re.search('(?<=published:)(.)*', str).group()
    except: pass
    try: e['author'] = re.search('(?<=author:)(.)*', str).group()
    except: pass
    try: e['category'] = re.search('(?<=category:)(.)*', str).group()
    except: pass
    try: e['url'] = re.search('(?<=url:)(.)*', str).group()
    except: pass
    try:
        e['uid'] = re.search('(?<=u-uid:)(.)*', str)
        if e['uid']:
            e['uid'] = e['uid'].group()
        else:
            e['uid'] = re.search('(?<=u-uid)(.)*', str).group()
    except: pass
    try: e['time-zone'] = re.search('(?<=time-zone:)(.)*', str).group()
    except: pass
    try: e['location'] = re.search('(?<=location:)(.)*', str).group()
    except: pass
    try: e['syndication'] = re.search('(?<=syndication:)(.)*', str).group()
    except: pass
    try: e['location_name'] = re.search('(?<=location-name:)(.)*', str).group()
    except: pass
    try: e['in_reply_to'] = re.search('(?<=in-reply-to:)(.)*', str).group()
    except:pass
    return e

def entry_re_write(data):
    data['title']
    entry = ''
    entry += "p-name:\n" \
             "title:{title}\n" \
             "slug:{slug}\n".format(title=data['title'], slug=data['slug'])
    entry += "summary:"+ str(data['summary']) + "\n"
    entry += "published:"+ str(data['published']) + "\n"
    entry += "category:" + str(data['category']) + "\n"
    entry += "url:"+ data['url'] + "\n"
    entry += "u-uid:" + data['uid'] + "\n"
    entry += "location:" + str(data['location'])+ "\n"
    entry += "location_name:" + str(data['location_name']) + "\n"
    entry += "location_id:" + str(data['location_id']) + "\n"
    entry += "in-reply-to:" + str(data['in_reply_to']) + "\n"
    entry += "syndication:" + str(data['syndication']) + "\n"
    entry += "content:" + data['content']+ "\n"
    if not os.path.isfile('data/'+data['url']+".md"):
        raise IOError('data/'+data['url']+'.md')                                      # if the file doesn't exist, this is being used wrong
    file_writer = open('data/'+data['url']+".md", 'wb')
    file_writer.write(entry.encode('utf-8'))
    file_writer.close()

for (dirpath, dirnames, filenames) in os.walk(path):
    for filename in filenames:
        if filename.endswith('.md'):
            try:
                entry = get_bare_file(os.sep.join([dirpath, filename]))
                print(os.sep.join([dirpath, filename]))
                if 'location' in entry.keys() and entry['location'] is not None and entry['location'] != 'None' and entry['location'] != '':
                    if 'location_name' not in entry.keys():
                        print(entry['location'], 'loc')
                        (lat,long) = entry['location'][4:].split(',')
                        geo_results = requests.get('http://api.geonames.org/findNearbyPlaceNameJSON?style=Full&radius=15&lat='+lat+'&lng='+long+'&username=kongaloosh')
                        name = geo_results.json()['geonames'][0]['name']
                        if geo_results.json()['geonames'][0]['adminName2']:
                            name += ", " + geo_results.json()['geonames'][0]['adminName2']
                        elif geo_results.json()['geonames'][0]['adminName1']:
                            name += ", " + geo_results.json()['geonames'][0]['adminName1']
                        else:
                            name += ", " + geo_results.json()['geonames'][0]['countryName']

                        entry['location_name'] = name
                        entry['location_id'] = geo_results.json()['geonames'][0]['geonameId']
                        entry_re_write(entry)
            except UnicodeDecodeError:
                pass
            except KeyError:
                pass
            except UnicodeEncodeError:
                pass


