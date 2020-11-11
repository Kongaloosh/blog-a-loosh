import ConfigParser
import re
import os
import sys
import markdown
from slugify import slugify
import json
from dateutil.parser import parse
from markdown_hashtags.markdown_hashtag_extension import HashtagExtension
from pysrc.file_management.markdown_album_pre_process import new_prefix
import logging
from PIL import Image
import numpy as np
from python_webmention.mentioner import get_entry_content
from markdown_albums.markdown_album_extension import AlbumExtension

sys.path.insert(0, os.getcwd()) # todo: this is bad.

__author__ = 'kongaloosh'

config = ConfigParser.ConfigParser()
config.read('config.ini')

logger = logging.getLogger(__name__)

# configuration
DATABASE = config.get('Global', 'Database')
DEBUG = config.get('Global', 'Debug')
SECRET_KEY = config.get('Global', 'DevKey')
USERNAME = config.get('SiteAuthentication', "Username")
PASSWORD = config.get('SiteAuthentication', 'password')
DOMAIN_NAME = config.get('Global', 'DomainName')
GEONAMES = config.get('GeoNamesUsername', 'Username')
FULLNAME = config.get('PersonalInfo', 'FullName')


def move_and_resize(from_location, to_blog_location, to_copy):
    """"
        Moves an image, scales it and stores a low-res with the blog post and a high-res in a long-term storage folder.
        :param loc: the location of an image
        :param loc: the date folder to which an image should be moved
        """

    to_blog_location = to_blog_location.lower()
    to_copy = to_copy.lower()

    if not os.path.exists(os.path.dirname(to_copy)):            # if the target directory doesn't exist ...
        os.makedirs(os.path.dirname(to_copy))                   # ... make it.
    img = Image.open(from_location)                             # open the image from the temp
    img_file = open(to_copy, "w")
    img.save(img_file, "JPEG")                                  # open the new location
    img_file.flush()
    os.fsync(img_file)
    img_file.close()
    img.close()


    img = Image.open(from_location)                             # open the image from the temp
    max_height = 3000                                           # maximum height

    if img.size[1] > img.size[0]:
        h_percent = (max_height / float(img.size[1]))               # calculate what percentage the new height is of the old
        if h_percent >= 1:
            w_size = 1
        else:
            w_size = int((float(img.size[0]) * float(h_percent)))  # calculate the new size of the width
        img = img.resize((w_size, max_height), Image.ANTIALIAS)     # translate the image
    else:
        w_percent = (max_height/ float(img.size[0]))              # calculate what percentage the new height is of the old
        if w_percent >= 1:
            h_size = 1
        else:
            h_size = int((float(img.size[1]) * float(h_percent)))  # calculate the new size of the width
        img = img.resize((max_height, h_size), Image.ANTIALIAS)     # translate the image
      
    if not os.path.exists(os.path.dirname(to_blog_location)):                    # if the blog's directory doesn't exist
       os.makedirs(os.path.dirname(to_blog_location))          # make it
    
    in_data = np.asarray(img, dtype=np.uint8)
    img_file = open(to_blog_location, "w")
    img.save(img_file, "JPEG")                                  # image save old_prefix
    img_file.flush()
    os.fsync(img_file)
    img_file.close()
    img.close()
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory
    os.remove(from_location)


def save_to_two(image,  to_blog_location, to_copy):
    """
    Saves two images: one image which is scaled down to optimize serving images, one which is put in a folder at
    original resolution for storage.
    args:
    :param image:
    :param to_blog_location:
    :param to_copy:
    :return:
    """
    to_blog_location = to_blog_location.lower()
    to_copy = to_copy.lower()

    if not os.path.exists(os.path.dirname(to_copy)):  # if the target directory doesn't exist ...
        os.makedirs(os.path.dirname(to_copy))  # ... make it.
    img = Image.open(image)  # open the image from the temp
    img_file = open(to_copy, "w")
    img.save(img_file, "JPEG")  # open the new location
    img_file.flush()
    os.fsync(img_file)
    img_file.close()
    img.close()

    img = Image.open(image)  # open the image from the temp
    max_height = 2000  # maximum height
    h_percent = (max_height / float(img.size[1]))  # calculate what percentage the new height is of the old
    if h_percent >= 1:
        w_size = 1
    else:
        w_size = int((float(img.size[0]) * float(h_percent)))  # calculate the new size of the width
    img = img.resize((w_size, max_height), Image.ANTIALIAS)  # translate the image
    if not os.path.exists(os.path.dirname(to_blog_location)):  # if the blog's directory doesn't exist
        os.makedirs(os.path.dirname(to_blog_location))  # make it
    in_data = np.asarray(img, dtype=np.uint8)
    img_file = open(to_blog_location, "w")
    img.save(img_file, "JPEG")  # image save old_prefix
    img_file.flush()
    os.fsync(img_file)
    img_file.close()
    img.close()
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory


def file_parser_json(filename, g=None, md=True):
    """Parses a json
    Args:
        filename: the filename (including path)
        g: the database connection
        md: boolean flag whether the markdown content should be parsed.
    """
    print(filename)
    entry = json.loads(open(filename, 'rb').read())
    try:
        entry['published'] = parse(entry['published'])      # parse the string for time
        if g and entry['published'] is None:                # if for some reason it's missing, infer from dbms
            entry['published'] = parse(g.db.execute("""
            SELECT published
            FROM entries
            WHERE slug = '{0}'
            """.format(entry['slug'])).fetchall()[0][0])
    except ValueError:
        pass    # this is a draft, so we don't need the published date

    if md and entry['content']:
        entry['raw_content'] = entry['content']
        entry['content'] = markdown.markdown(entry['content'], extensions=['mdx_math', AlbumExtension(), HashtagExtension(), 'fenced_code'])

    elif entry['content'] is None:          # if we have no text for this
        entry['content'] = ''               # give it an empty string so it renders the post properly
        entry['raw_content'] = ''           # give it an empty string so it renders the post properly

    if entry['in_reply_to']:
        # if the post is a response,
        in_reply_to = []
        if type(entry['in_reply_to']) != list:  # if the reply_tos isn't a list
            entry['in_reply_to'] = [reply_to.strip() for reply_to in entry['in_reply_to'].split(',')]  # split reply_tos
        for i in entry['in_reply_to']:      # for all the replies we have...
            # todo: THIS SHOULD BE ASYNC!
            if type(i) == dict:             # which are not images on our site...
                in_reply_to.append(i)
            elif i.startswith('http://127.0.0.1:5000'):     # if localhost self-reference, parse the entry
                in_reply_to.append(file_parser_json(i.replace('http://127.0.0.1:5000/e/', 'data/', 1) + ".json"))
            elif i.startswith('https://kongaloosh.com/'):   # if self-reference, parse the entry
                in_reply_to.append(file_parser_json(i.replace('https://kongaloosh.com/e/', 'data/', 1) + ".json"))
            elif i.startswith('http'):                  # which are not data resources on our site...
                in_reply_to.append({'url':i})
                # in_reply_to.append(get_entry_content(i))   # try to get the content; at minimum returns url
        entry['in_reply_to'] = in_reply_to

    return entry


def create_post_from_data(data):
    """cleans a dictionary based on posted form info and preps for json dump."""
    # 1. slugify
    if data['slug']:                                # if there's already a slug
        slug = data['slug']                         # ... just use the slug
    else:                                           # ... otherwise make a slug
        if data['title']:                           # is it an article?
            slug = slugify(data['title'])[:10]      # ... grab the slug
        else:                                       # ... otherwise we make a slug from post content
            try:
                slug = (data['content'].split('.')[0])  # we make the slug from the first sentance
                slug = slugify(slug)[:10]               # slugify the slug
            except AttributeError:                      # if no content exists use the date
                slug = slugify("{year}-{month}-{day}".format(
                        year=str(data['published'].year),
                        month=str(data['published'].month),
                        day=str(data['published'].day)))             # turn date into file-path)
        data['u-uid'] = slug
        data['slug'] = slug
    # 2. parse categories
    try:                                            # if we have a category in the
        if data['category']:                        # comes in as a string, so we need to parse it
            data['category'] = [i.strip() for i in data['category'].lower().split(",")]
    except AttributeError:
        pass
    # 3. parse reply tos
    if isinstance(data['in_reply_to'], basestring):
        data['in_reply_to'] = [reply.strip() for reply in data['in_reply_to'].split(',')]  # turn it into a list
    return data


def create_json_entry(data, g, draft=False, update=False):
    """
    creates a json entry based on recieved dictionary, then creates a human-readable .md alongisde it.
    """

    data = create_post_from_data(data)

    if draft:   # whether or not this is a draft changes the location saved
        file_path = "drafts/"
        data['url'] = '/drafts/' + data['slug']

    else:       # if it's not a draft we need to prep for saving
        date_location = "{year}/{month}/{day}/".format(
                        year=str(data['published'].year),
                        month=str(data['published'].month),
                        day=str(data['published'].day))             # turn date into file-path
        file_path = "data/" + date_location                         # where we'll save the new entry
        data['url'] = '/e/' + date_location + data['slug']

    if not os.path.exists(file_path):                               # if the path doesn't exist, make it
        os.makedirs(os.path.dirname(file_path))

    total_path = file_path+"{slug}".format(slug=data['slug'])       # path including filename

    # check to make sure that the .json and human-readable versions do not exist currently
    if not os.path.isfile(total_path+'.md') and not os.path.isfile(total_path+'.json') or update:
        # Find all the multimedia files which were added with the posts
        for (key, extension) in [
                ('photo', '.jpg')]:
            # todo: expand to other filetypes
            try:
                if not os.path.isfile(total_path + extension) and data[key]:  # if there is no photo already
                    # if the image is a location ref
                    if type(data[key]) == unicode and data[key].startswith("/images/"):
                        # move the image and resize it
                        move_and_resize(
                            new_prefix + data[key][len('/images/'):],  # we remove the head to get rid of preceeding "/images/"
                            total_path + extension,
                            new_prefix + total_path + extension
                        )
                    else:   # if we have a buffer with the data already present, simply save and move it.
                        save_to_two(
                            data[key],
                            total_path + extension,
                            new_prefix + total_path + extension)
                    data[key] = total_path + extension              # update the dict to a location refrence
            except KeyError:
                pass

        try:
            if data['travel']['map']:
                file_writer = open(total_path + "-map.png", 'w')  # save in the same place as post with map naming and as .png
                file_writer.write(data['travel']['map'])     # save the buffer from the request
                file_writer.close()
                data['travel']['map'] = total_path + "-map.png"    # where the post should point to fetch the map
        except KeyError:
            pass

        data['published'] = data['published'].__str__()             # dump to string for serialization
        file_writer = open(total_path+".json", 'w')                 # open and dump the actual post meta-data
        file_writer.write(json.dumps(data))
        file_writer.close()

        if not draft and not update and g:                         # if this isn't a draft, put it in the dbms
            g.db.execute(
                """
                insert into entries
                (slug, published, location) values (?, ?, ?)
                """, [data['slug'], data['published'], total_path]
                         )
            g.db.commit()
            if data['category']:
                for c in data['category']:
                    g.db.execute('insert or replace into categories (slug, published, category) values (?, ?, ?)',
                                 [data['slug'], data['published'], c])
                    g.db.commit()

            # create_entry_markdown(data, total_path)                 # also create md version.
        return data['url']

    else:
        return "/already_made"                                     # a post of this name already exists


def update_json_entry(data, old_entry, g, draft=False):
    """
    Update old entry based on differences in new entry and saves file.
    Calls create_json_entry after the appropriate dbms manipulation is finished to actually save the entry.

    Args:
        data: the new entry the old entry is updated with
        old_entry: the old entry which is being updated
        g: dbms cursor
        draft: flag indicating whether we're updating a draft or an already submitted post
    """

    # 1. ensure that privileged old info isn't over-written
    for key in ['slug', 'u-uid', 'url', 'published']:               # these things should never be updated
        data[key] = old_entry[key]

    # 2. remove categories if they exist and replace (if not draft)
    if data['category'] and not draft and g:                        # if categories exist, update them
        # parse the categories into a list, but only if they're a string
        try:
            data['category'] = [i.strip() for i in data['category'].lower().split(",")]
        except AttributeError:
            pass
        try:
            # remove all previous categories from the db
            for c in old_entry['category']:
                g.db.execute(
                    '''
                    DELETE FROM categories
                    WHERE slug = '{0}' AND category = '{1}';
                    '''.format(data['slug'], c)
                )
        except TypeError:
            pass

        # put the new categories into the db
        for c in data['category']:      # parse the categories into a list and add to dbms
            g.db.execute('''
                insert or replace into categories (slug, published, category) values (?, ?, ?)''',
                 [old_entry['slug'], old_entry['published'], c])
            g.db.commit()

    # 3. check for mentions
    if isinstance(data['in_reply_to'], basestring):
        data['in_reply_to'] = [reply.strip() for reply in data['in_reply_to'].split(',')]  # turn it into a list

    # 4. for all the remaining data, update the old entry with the new entry.
    for key in data.keys():
        if data[key]:
            old_entry[key] = data[key]
    create_json_entry(data=old_entry, g=g, draft=draft, update=True)


def create_entry_markdown(data, path):
    """
    Creates a markdown post given a path and the data
    :param data: dictionary containing the information to be posted
    :param path: the path where we're creating the .md
    """
    for key in data.keys():
        if data[key] is None:
            data[key] = ''
    entry = ''
    entry += "p-name:\n" \
             "title:{title}\n" \
             "slug:{slug}\n".format(title=data['title'], slug=data['slug'])
    entry += "summary:" + str(data['summary']) + "\n"
    entry += "published:" + str(data['published']) + "\n"
    try:
        entry += "category:" + ', '.join(data['category']) + "\n"
    except TypeError:
        entry += "category:" + data['category']
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
        e['object']['content'] = markdown.markdown(e['content'], extensions=['mdx_math', AlbumExtension(), HashtagExtension()])
        if e['object']['content'] is None:
            e['object']['content'] = markdown.markdown(re.search('(?<=content:)((.)|(\n))*$', str).group(), extensions=['mdx_math', AlbumExtension(), HashtagExtension()])
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
