import os
import sqlite3
import re

__author__ = 'kongaloosh'

path = 'data/'

url_bit = "kongaloosh.com/e/"

list_of_files = {}
conn = sqlite3.connect('kongaloosh.db')
g = conn.cursor()


def get_bare_file(filename: str) -> dict:
    """ for a given entry, finds all of the info we want to display """
    f = open(filename, 'r')
    str = f.read()
    # str = str.decode('utf-8')  # This line is commented out, so we'll leave it as is
    e = {}
    try:
        e['title'] = re.search(r'(?<=title:).*', str).group()
    except AttributeError:
        e['title'] = None
    try:
        e['slug'] = re.search(r'(?<=slug:).*', str).group()
    except AttributeError:
        e['slug'] = None
    try:
        e['published'] = re.search('(?<=published:)(.)*', str)
        if e['published']:
            e['published'] = e['published'].group()
    except AttributeError:
        pass

    try:
        e['category'] = re.search('(?<=category:)(.)*', str)
        if e['category']:
            e['category'] = e['category'].group()
    except AttributeError:
        pass

    try:
        e['url'] = re.search('(?<=url:)(.)*', str)
        if e['url']:
            e['url'] = e['url'].group()
    except AttributeError:
        pass
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
