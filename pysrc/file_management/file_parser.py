import ConfigParser
import pickle
import re
import os
import sys
import markdown
from slugify import slugify
import json
from dateutil.parser import parse
sys.path.insert(0, os.getcwd())
from pysrc.webmention.mentioner import send_mention
from pysrc.file_management.markdown_album_extension import AlbumExtension

__author__ = 'alex'

config = ConfigParser.ConfigParser()
config.read('config.ini')

# configuration
DATABASE = config.get('Global', 'Database')
DEBUG = config.get('Global', 'Debug')
SECRET_KEY = config.get('Global', 'DevKey')
USERNAME = config.get('SiteAuthentication', "Username")
PASSWORD = config.get('SiteAuthentication', 'password')
DOMAIN_NAME = config.get('Global', 'DomainName')
GEONAMES = config.get('GeoNamesUsername', 'Username')
FULLNAME = config.get('PersonalInfo', 'FullName')


def file_parser_json(filename):
    entry = json.loads(open(filename, 'rb').read())
    entry['published'] = parse(entry['published'])
    return entry


def create_json_entry(data, g, draft=False):
    if data['name']:                            # is it an article?
        title = data['name']                    # we make the slug from the title
        slug = title
    else:                                       # otherwise we make a slug from post content
        slug = (data['content'].split('.')[0])  # we make the slug from the first sentance
    slug = slugify(slug)                        # slugify the slug
    data['u-uid'] = slug
    data['slug'] = slug

    date_location = "{year}/{month}/{day}/".format(
                        year=str(data['published'].year),
                        month=str(data['published'].month),
                        day=str(data['published'].day))             # turn date into filepath

    if data['category']:
        data['category'] = data['category'].strip().split(",")  # comes in as a string, so we need to parse it

    if draft:                                   # whether or not this is a draft changes the location saved
        file_path = "drafts/"
        data['url'] = '/drafts/' + slug
    else:
        file_path = "data/" + date_location
        data['url'] = '/e/' + date_location + slug

    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path))

    total_path = file_path+"{slug}".format(slug=slug)

    # check to make sure that the .json and human-readable versions do not exist currently
    if not os.path.isfile(total_path+'.md') and not os.path.isfile(total_path+'.json'):
        # Find all the multimedia files which were added with the posts

        for (key, extension) in [
                # (data['video'], '.mp4'),
                # (data['audio'], '.mp3'),
                ('photo', '.jpg')]:

            if not os.path.isfile(total_path + extension) and data[key]:  # if there is no photo already
                print('here', data['key'])
                file_writer = open(total_path + extension, 'wb')          # find a location to put the media
                file_writer.write(data[key])                              # write the media to a file
                file_writer.close()
                data[key] = total_path + extension
            elif os.path.isfile(total_path + extension):
                data[key] = total_path + extension                            # update the dict to a location refrence

        data['published'] = data['published'].__str__()
        print(data)
        file_writer = open(total_path+".json", 'wb')                # open and dump the actual post meta-data
        file_writer.write(json.dumps(data))
        file_writer.close()

        if not draft:                                               # if this isn't a draft, put it in the dbms
            g.db.execute(
                """
                insert into entries
                (slug, published, location) values (?, ?, ?)
                """, [slug, data['published'], total_path]
                         )
            g.db.commit()

            if data['category']:
                for c in data['category'].strip().split(','):
                    g.db.execute('insert into categories (slug, published, category) values (?, ?, ?)',
                                 [slug, data['published'], c])
                    g.db.commit()

            create_entry_markdown(data, total_path)                 # if this isn't a draft make a human-readable vers
        return data['url']
    else:
        return "/already_made"                                      # a post of this name already exists


def update_json_entry(data, old_entry, g):
    if data['category']:
        data['category'] = data['category'].strip().split(',')
        for c in data['category']:
            g.db.execute('insert into categories (slug, published, category) values (?, ?, ?)',
                 [old_entry['slug'], old_entry['published'], c])
            g.db.commit()

    for key in data.keys():
        if data[key]:
            old_entry[key] = data[key]
    create_json_entry(data, g)


def create_entry_markdown(data, path):
    entry = ''
    entry += "p-name:\n" \
             "title:{title}\n" \
             "slug:{slug}\n".format(title=data['name'], slug=data['slug'])
    entry += "summary:" + str(data['summary']) + "\n"
    entry += "published:" + str(data['published']) + "\n"
    entry += "category:" + str(data['category']) + "\n"
    entry += "url:" + data['url'] + "\n"
    entry += "u-uid:" + data['url'] + "\n"
    entry += "location:" + str(data['location']) + "\n"
    entry += "location_name:" + str(data['location_name']) + "\n"
    entry += "location_id:" + str(data['location_id']) + "\n"
    entry += "in-reply-to:" + str(data['in_reply_to']) + "\n"
    entry += "repost-of:" + str(data['repost-of']) + "\n"
    entry += "syndication:" + str(data['syndication']) + "\n"
    entry += "content:" + data['content'] + "\n"
    print(path)
    total_path = path + ".md"
    file_writer = open(total_path, 'wb')
    file_writer.write(entry.encode('utf-8'))
    file_writer.close()


def activity_stream_parser(filename):
    f = open(filename, 'r')
    str = f.read()
    str = str.decode('utf-8')
    e = {}
    e['actor'] = {}
    e['actor']['image']
    e['actor']['@id'] = DOMAIN_NAME
    e['actor']['type'] = 'person'
    e['actor']['name'] = FULLNAME
    e['actor']['image']['type'] = 'Link'
    e['actor']['image']['href'] = 'http://' + DOMAIN_NAME +'/static/img/profile.jpg'
    e['actor']['image']['mediaType'] = 'image/jpeg'
    e['@context'] = "https://www.w3.org/ns/activitystreams"

    try:
        e['object']['nm'] = re.search('(?<=title:)(.)*', str).group()
    except KeyError:
        pass

    try:
        e['object']['summary'] = re.search('(?<=summary:)(.)*', str).group()
    except KeyError:
        pass

    try:
        e['object']['content'] = re.search('(?<=content:)((?!category:)(?!published:)(.)|(\n))*', str).group()
        e['object']['content'] = markdown.markdown(e['content'], extensions=[AlbumExtension(), 'pysrc.file_management.markdown_album_extension'])
        if e['object']['content'] is None:
            e['object']['content'] = markdown.markdown(re.search('(?<=content:)((.)|(\n))*$', str).group(), extensions=[AlbumExtension(), 'pysrc.file_management.markdown_album_extension'])
    except KeyError:
        pass

    try:
        date = parse(re.search('(?<=published:)(.)*', str).group())
        e['published'] = date.date()
    except KeyError:
        pass

    try:
        e['category'] = re.search('(?<=category:)(.)*', str).group().split(',')
    except KeyError:
        pass

    try:
        e['object']['id'] = re.search('(?<=url:)(.)*', str).group()
    except KeyError:
        pass

    try:
        e['object']['location'] = re.search('(?<=location:)(.)*', str).group()
    except KeyError:
        pass

    try:
        e['object']['location_name'] = re.search('(?<=location_name:)(.)*', str).group()
    except KeyError:
        pass

    try:
        replies = re.search('(?<=in-reply-to:)(.)*', str).group()
        if replies != 'None':
            e['object']['inReplyTo'] = []
            replies = replies.split(',')
        else:
            e['object']['inReplyTo'] = replies
        for site in replies:
            if site.startswith('http'):         # if it's an external site, we simply add it
                e['object']['inReplyTo'].append(site)
            elif site.startswith('/'):          # if it's a local id, we append it with the site's url
                e['object']['inReplyTo'].append(file_parser('data'+site+'.md'))
    except KeyError:
        pass

    if os.path.exists(filename.split('.md')[0]+".jpg"):
        e['object']['image']['mediaType'] = 'image/jpeg'
        e['object']['image']['href'] = "http://"+DOMAIN_NAME+"/data/" + filename.split('.md')[0]+".jpg"
        e['object']['image']['type'] = "Link"