import ConfigParser
import pickle
import re
import os
import sys
import markdown
from slugify import slugify
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

def file_parser(filename):
    """ for a given entry, finds all of the info we want to display """
    # todo: clean up all these horrible exceptions
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
        e['content'] = re.search('(?<=content:)((?!category:)(?!published:)(.)|(\n))*', str).group()
        e['content'] = markdown.markdown(e['content'], extensions=[AlbumExtension(), 'pysrc.file_management.markdown_album_extension'])
        if e['content'] == None:
            e['content'] = markdown.markdown(re.search('(?<=content:)((.)|(\n))*$', str).group(), extensions=[AlbumExtension(), 'pysrc.file_management.markdown_album_extension'])
    except: pass
    try:
        date = parse(re.search('(?<=published:)(.)*', str).group())
        e['published'] = date.date()
    except: pass
    try: e['author'] = re.search('(?<=author:)(.)*', str).group()
    except: pass
    try: e['category'] = re.search('(?<=category:)(.)*', str).group().split(',')
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
    try:
        e['location'] = re.search('(?<=location:)(.)*', str).group()
    except: pass
    try: e['syndication'] = re.search('(?<=syndication:)(.)*', str).group()
    except: pass
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
        for site in replies:
            if site.startswith('http'):         # if it's an external site, we simply add it
                e['in_reply_to'].append(site)
            elif site.startswith('/'):          # if it's a local id, we append it with the site's url
                e['in_reply_to'].append(file_parser('data'+site+'.md'))
    except:pass
    if os.path.exists(filename.split('.md')[0]+".jpg"):
        e['photo'] = filename.split('.md')[0]+".jpg" # get the actual file

    return e


def get_bare_file(filename):
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
    try: e['location_name'] = re.search('(?<=location_name:)(.)*', str).group()
    except: pass
    try: e['location_id'] = re.search('(?<=location_id:)(.)*', str).group()
    except: pass
    try: e['in_reply_to'] = re.search('(?<=in-reply-to:)(.)*', str).group()
    except:pass
    return e


def editEntry(data, old_entry, g):
    entry = ''
    title = data['name']
    slug = old_entry['slug']

    entry += "p-name:\n" \
             "title:{title}\n" \
             "slug:{slug}\n".format(title=title, slug=slug)

    entry += "summary:" + str(data['summary']) + "\n"
    entry += "published:" + str(old_entry['published']) + "\n"
    entry += "category:" + str(data['category']) + "\n"
    entry += "url:"+ old_entry['url'] + "\n"
    entry += "u-uid:" + str(old_entry['uid']) + "\n"
    entry += "location:" + str(data['location'])+ "\n"
    entry += "location_name:" + str(data['location_name']) + "\n"
    entry += "location_id:" + str(data['location_id']) + "\n"
    entry += "in-reply-to:" + str(data['in-reply-to']) + "\n"
    entry += "repost-of:" + str(data['repost-of']) + "\n"
    entry += "syndication:" + str(old_entry['syndication']) + "\n"
    entry += "content:" + data['content'] + "\n"

    total_path = old_entry['url']

    print(os.path.isfile('data' + total_path + '.md'),os.path.isfile('drafts' + total_path + '.md'))

    if os.path.isfile('data' + total_path + '.md'):
        file_writer = open('data' + total_path + ".md", 'wb')
        file_writer.write(entry.encode('utf-8'))
        file_writer.close()
        if data['category']:
            for c in data['category'].split(','):
                if c is not 'None':
                    cur = g.db.execute(
                         """
                         SELECT *
                         FROM categories
                         WHERE slug = '{a}' AND published = '{b}' AND category = '{c}'
                         """.format(a=old_entry['slug'], b=old_entry['published'], c=c))

                    a = [row for (row) in cur.fetchall()]
                    if a == []:
                        g.db.execute('insert into categories (slug, published, category) values (?, ?, ?)',
                                     [old_entry['slug'], old_entry['published'], c])
                        g.db.commit()

        return '/e' + old_entry['url']
    elif os.path.isfile('drafts' + total_path + '.md'):                 # if this is a draft
        file_writer = open('drafts' + total_path + ".md", 'wb')
        file_writer.write(entry.encode('utf-8'))
        file_writer.close()

        return '/drafts' + old_entry['url']
    else:
        return "/404"


def create_entry(data, g, image=None, video=None, audio=None, draft=False):
    entry = ''
    if data['name']:                # is it an article?
        title = data['name']
        slug = title
    else:                                       # otherwise we make a slug from post content
        slug = (data['content'].split('.')[0])
        title = None

    slug = slugify(slug)

    entry += "p-name:\n" \
             "title:{title}\n" \
             "slug:{slug}\n".format(title=title, slug=slug)

    entry += "summary:" + str(data['summary']) + "\n"
    entry += "published:" + str(data['published']) + "\n"
    entry += "category:" + str(data['category']) + "\n"

    if draft:
        entry += "url:"+'/{slug}'.format(
            slug=str(slug)) + "\n"

        entry += "u-uid:" + '/{slug}'.format(
            slug=str(slug)) + "\n"

        file_path = "drafts/"
    else:
        entry += "url:"+'/{year}/{month}/{day}/{slug}'.format(
            year=str(data['published'].year),
            month=str(data['published'].month),
            day=str(data['published'].day),
            slug=str(slug)) + "\n"

        entry += "u-uid:" + '/{year}/{month}/{day}/{slug}'.format(
            year=str(data['published'].year),
            month=str(data['published'].month),
            day=str(data['published'].day),
            slug=str(slug)) + "\n"

        file_path = "data/{year}/{month}/{day}/".format(
            year=str(data['published'].year),
            month=str(data['published'].month),
            day=str(data['published'].day))

        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path))

    total_path = file_path+"{slug}".format(slug=slug)

    entry += "location:" + str(data['location']) + "\n"
    entry += "location_name:" + str(data['location_name']) + "\n"
    entry += "location_id:" + str(data['location_id']) + "\n"
    entry += "in-reply-to:" + str(data['in-reply-to']) + "\n"
    entry += "repost-of:" + str(data['repost-of']) + "\n"
    entry += "syndication:" + str(data['syndication']) + "\n"
    entry += "content:" + data['content']+ "\n"

    if not os.path.isfile(total_path+'.md'):
        print(total_path+".md")
        file_writer = open(total_path+".md", 'wb')
        file_writer.write(entry.encode('utf-8'))
        file_writer.close()
        if image:
            file_writer = open(total_path+".jpg", 'wb')
            file_writer.write(image)
            file_writer.close()

        if video:
            file_writer = open(total_path+".mp4", 'wb')
            file_writer.write(image)
            file_writer.close()

        if audio:
            file_writer = open(total_path+".mp3", 'wb')
            file_writer.write(image)
            file_writer.close()

        if not draft:
            g.db.execute('insert into entries (slug, published, location) values (?, ?, ?)',
                         [slug, data['published'], total_path]
                         )
            g.db.commit()

            if data['category']:
                for c in data['category'].split(','):
                    g.db.execute('insert into categories (slug, published, category) values (?, ?, ?)',
                                 [slug, data['published'], c])
                    g.db.commit()

        if not draft:
            source = '/e/{year}/{month}/{day}/{slug}'.format(
                year = str(data['published'].year),
                month = str(data['published'].month),
                day = str(data['published'].day),
                slug = str(slug))

            try:
                for reply in data['in-reply-to']:
                    send_mention('http://kongaloosh.com' + source, reply)
            except TypeError:
                pass
            return source
        else:
            return "drafts/"+slug
    else:
        return "/already_made"


def entry_re_write(data):
    pickle.dump(data, open('data.pkl','w'))
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
    entry += "in-reply-to:" + str(data['in_reply_to']) + "\n"
    #entry += "repost-of:" + str(data['repost-of']) + "\n"
    entry += "syndication:" + str(data['syndication']) + "\n"
    entry += "content:" + data['content']+ "\n"
    if not os.path.isfile('data/'+data['url']+".md"):
        raise IOError('data/'+data['url']+'.md')                                      # if the file doesn't exist, this is being used wrong
    file_writer = open('data/'+data['url']+".md", 'wb')
    file_writer.write(entry.encode('utf-8') )
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