from slugify import slugify
import os
import json
import re
import markdown
from dateutil.parser import parse

__author__ = 'kongaloosh'


def create_json_entry(data):
    needed_tags = {
        'h': None,
        'name': None,
        'summary': None,
        'content': None,
        'published': None,
        'updated': None,
        'category': None,
        'slug': None,
        'location': None,
        'location_name': None,
        'location_id': None,
        'in_reply_to': None,
        'repost-of': None,
        'syndication': None,
        'photo': None
    }
    for key in needed_tags.keys():
        try:
            data[key]
        except KeyError:
            data[key] = None


    if data['slug']:
        slug = data['slug']
    else:
        if data['name']:                            # is it an article?
            title = data['name']                    # we make the slug from the title
            slug = title
        else:                                       # otherwise we make a slug from post content
            slug = (data['content'].split('.')[0])  # we make the slug from the first sentance
            slug = slugify(slug)                        # slugify the slug
        data['u-uid'] = slug
        data['slug'] = slug

    try:
        if data['category']:
            data['category'] = data['category'].strip().split(",")  # comes in as a string, so we need to parse it
    except AttributeError:
        data['category'] = list(data['category'])

    date_location = "{year}/{month}/{day}/".format(
                    year=str(data['published'].year),
                    month=str(data['published'].month),
                    day=str(data['published'].day))             # turn date into filepath
    file_path = "data/" + date_location
    data['url'] = '/e/' + date_location + slug

    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path))

    total_path = file_path+"{slug}".format(slug=slug)

    # check to make sure that the .json and human-readable versions do not exist currently
    if os.path.isfile(total_path+'.json'):
        print('path', total_path + ".json")
        # Find all the multimedia files which were added with the posts
        data['published'] = data['published'].__str__()
        file_writer = open(total_path+".json", 'wb')                # open and dump the actual post meta-data
        file_writer.write(json.dumps(data))
        file_writer.close()


def file_parser(filename):
    """ for a given entry, finds all of the info we want to display """
    # todo: clean up all these horrible exceptions
    f = open(filename, 'r')
    str = f.read()
    str = str.decode('utf-8')
    e = {}
    e['title'] = re.search('(?<=title:)(.)*', str).group()
    e['slug'] = re.search('(?<=slug:)(.)*', str).group()
    e['summary'] = re.search('(?<=summary:)(.)*', str).group()
    e['content'] = re.search('(?<=content:)((?!category:)(?!published:)(.)|(\n))*', str).group()
    date = parse(re.search('(?<=published:)(.)*', str).group())
    e['published'] = date.date()
    try:
        e['author'] = re.search('(?<=author:)(.)*', str).group()
    except AttributeError:
        e['author'] = None
    e['category'] = re.search('(?<=category:)(.)*', str).group().split(',')
    for c in e['category']:
        if c == "None":
            e['category'] = None
    e['url'] = re.search('(?<=url:)(.)*', str).group()
    e['u-uid'] = e['url']
    e['location'] = re.search('(?<=location:)(.)*', str).group()
    e['syndication'] = re.search('(?<=syndication:)(.)*', str).group()
    try: e['location_name'] = re.search('(?<=location_name:)(.)*', str).group()
    except: pass
    try: e['location_id'] = re.search('(?<=location_id:)(.)*', str).group()
    except: pass
    try:
        replies = re.search('(?<=in-reply-to:)(.)*', str).group()
        if replies != 'None':
            e['in_reply_to'] = []
            replies = replies.split(',')
        else:
            e['in_reply_to'] = replies
    except:pass
    if os.path.exists(filename.split('.md')[0]+".jpg"):
        e['photo'] = filename.split('.md')[0]+".jpg" # get the actual file
    for key in e.keys():
        if e[key] == '' or e[key] == 'None':
            print(key)
            e[key] = None
    return e

path = 'data/'

def fix():
    for (dirpath, dirnames, filenames) in os.walk(path):
        for filename in filenames:
            if filename.endswith('.md'):
                # print(os.sep.join([dirpath, filename]))
                try:
                    entry = file_parser(os.sep.join([dirpath, filename]))
                    entry['u-uid'] = '/e' + entry['u-uid']
                    entry['url'] = '/e' + entry['url']
                    create_json_entry(entry)
                except (AttributeError, UnicodeDecodeError):
                    pass

if __name__ == '__main__':
    e = file_parser('data/2015/11/20/test-notes.md')
    print(e)
    # e = file_parser('data/2015/7/25/albums.md')
    # create_json_entry(e)
    fix()