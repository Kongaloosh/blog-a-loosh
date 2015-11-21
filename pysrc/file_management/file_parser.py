import pickle
import re
import os
import sys
import markdown2
from slugify import slugify
from dateutil.parser import parse
sys.path.insert(0, os.getcwd())
from pysrc.webmention.mentioner import send_mention
from geopy.geocoders import GoogleV3
from geopy.exc import GeocoderQuotaExceeded, GeocoderQueryError
__author__ = 'alex'


def file_parser(filename):
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
        e['content'] = re.search('(?<=content:)((?!category:)(?!published:)(.)|(\n))*', str).group()
        e['content'] = markdown2.markdown(e['content'], extras=['tables','fenced_code'])
        if e['content'] == None:
            e['content'] = markdown2.markdown(re.search('(?<=content:)((.)|(\n))*$', str).group(), extras=['tables','fenced-code-blocks'])
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
    try: e['location_name'] = re.search('(?<=location-name:)(.)*', str).group()
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

    try:
        if e['location'] != 'None':
            geolocator = GoogleV3(api_key='AIzaSyB28OwVWQ-OBIlQGRHzFy5-_EMx0wTN9IM')
            geolocator.reverse("40.752067, -73.977578")
            try:
                location = geolocator.reverse(e['location'].split(':')[1])[0]
            except IndexError:
                location = geolocator.reverse(e['location'])
            geo = ''
            for i in location.raw['address_components']:
                try:
                    # app.logger.info("home-star")
                    if 'locality' in i['types'] or 'country' in i['types']:
                        geo += (i['long_name'] + ' ')
                except KeyError:
                    pass
            e['location'] = geo
    except (GeocoderQuotaExceeded, GeocoderQueryError):
        pass

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
    try: e['location_name'] = re.search('(?<=location-name:)(.)*', str).group()
    except: pass
    try: e['in_reply_to'] = re.search('(?<=in-reply-to:)(.)*', str).group()
    except:pass
    return e


def editEntry(data, old_entry, g):
    # todo: delete unwanted categories
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
    entry += "in-reply-to:" + str(data['in-reply-to']) + "\n"
    entry += "repost-of:" + str(data['repost-of']) + "\n"
    entry += "syndication:" + str(data['syndication']) + "\n"
    entry += "content:" + data['content'] + "\n"

    total_path = old_entry['url']
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
    else:
        return "This doesn't exist"


def createEntry(data, g, image=None, video=None, audio=None):
    entry = ''
    if not data['name'] == None:    #is it an article
        title = data['name']
        slug = title
    else:
        slug = (data['content'].split('.')[0])
        title = None

    slug = slugify(slug)

    entry += "p-name:\n" \
             "title:{title}\n" \
             "slug:{slug}\n".format(title=title, slug=slug)

    entry += "summary:"+ str(data['summary']) + "\n"
    entry += "published:"+ str(data['published']) + "\n"
    entry += "category:" + str(data['category']) + "\n"
    entry += "url:"+'/{year}/{month}/{day}/{slug}'.format(
        year = str(data['published'].year),
        month = str(data['published'].month),
        day = str(data['published'].day),
        slug = str(slug)) + "\n"
    entry += "u-uid:" + '/{year}/{month}/{day}/{slug}'.format(
        year = str(data['published'].year),
        month = str(data['published'].month),
        day = str(data['published'].day),
        slug = str(slug)) + "\n"
    entry += "location:" + str(data['location'])+ "\n"
    entry += "in-reply-to:" + str(data['in-reply-to']) + "\n"
    entry += "repost-of:" + str(data['repost-of']) + "\n"
    entry += "syndication:" + str(data['syndication']) + "\n"
    entry += "content:" + data['content']+ "\n"

    time = data['published']
    file_path = "data/{year}/{month}/{day}/".format(year=time.year, month=time.month, day=time.day)
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path))

    total_path = file_path+"{slug}".format(slug=slug)

    if not os.path.isfile(total_path+'.md'):
        file_writer = open(total_path+".md", 'wb')
        file_writer.write(entry.encode('utf-8') )
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

        g.db.execute('insert into entries (slug, published, location) values (?, ?, ?)',
                     [slug, data['published'], total_path]
                     )
        g.db.commit()

        if data['category']:
            for c in data['category'].split(','):
                g.db.execute('insert into categories (slug, published, category) values (?, ?, ?)',
                             [slug, data['published'], c])
                g.db.commit()

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
        return "this has already been made"


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
        raise IOError('data/'+data[url]+'.md')                                      # if the file doesn't exist, this is being used wrong
    file_writer = open('data/'+data['url']+".md", 'wb')
    file_writer.write(entry.encode('utf-8') )
    file_writer.close()

