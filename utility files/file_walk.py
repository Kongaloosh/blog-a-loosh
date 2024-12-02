import os
import sqlite3
import re

__author__ = 'kongaloosh'

path = 'data/'

url_bit = "kongaloosh.com/e/"

list_of_files = {}
conn = sqlite3.connect('kongaloosh.db')
g = conn.cursor()


def get_bare_file(filename):
    """ for a given entry, finds all of the info we want to display """
    f = open(filename, 'r')
    str = f.read()
    # str = str.decode('utf-8')
    e = {}
    try: e['title'] = re.search('(?<=title:)(.)*', str).group()
    except: pass
    try: e['slug'] = re.search('(?<=slug:)(.)*', str).group()
    except: pass
    try:
        e['published'] = re.search('(?<=published:)(.)*', str).group()
    except: pass
    try: e['category'] = re.search('(?<=category:)(.)*', str).group()
    except: pass
    try: e['url'] = re.search('(?<=url:)(.)*', str).group()
    except: pass
    return e


for (dirpath, dirnames, filenames) in os.walk(path):
    for filename in filenames:
        if filename.endswith('.md'):
            print(os.sep.join([dirpath, filename]))

            try:
                entry = get_bare_file(os.sep.join([dirpath, filename]))

                g.execute('insert into entries (slug, published, location) values (?, ?, ?)',
                             [entry['slug'], entry['published'], path + entry['url']]
                             )
                conn.commit()
                if entry['category']:
                    for c in entry['category'].split(','):
                        g.execute('insert into categories (slug, published, category) values (?, ?, ?)',
                                     [entry['slug'], entry['published'], c])
                        conn.commit()
            except:
                pass
