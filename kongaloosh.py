#!/usr/bin/python
# coding: utf-8
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, Response, make_response, jsonify
from contextlib import closing
import os
import math
from datetime import datetime
from jinja2 import Environment
from dateutil.parser import parse
from pysrc.webmention.extractor import get_entry_content
from pysrc.posse_scripts import tweeter
from pysrc.file_management.file_parser import create_json_entry, update_json_entry, file_parser_json
from pysrc.authentication.indieauth import checkAccessToken
from pysrc.webmention.webemention_checking import get_mentions
from rdflib import Graph, plugin
import pickle
from threading import Timer
import requests
import json
from slugify import slugify
import ConfigParser
import re
import requests
from pysrc.file_management.markdown_album_pre_process import move, run
from PIL import Image, ExifTags

jinja_env = Environment(extensions=['jinja2.ext.with_'])

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

print(DATABASE, USERNAME, PASSWORD, DOMAIN_NAME)

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config['STATIC_FOLDER'] = os.getcwd()
cfg = None


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.route('/')
def show_entries():
    """ The main view: presents author info and entries. """

    entries = []                            # store the entries which will be presented
    cur = g.db.execute(                     # grab in order of newest
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )

    for (row,) in cur.fetchall():           # iterate over the results
        if os.path.exists(row + ".json"):   # if the file fetched exists, append the parsed details
            entries.append(file_parser_json(row + ".json"))

    try:
        entries = entries[:10]              # get the 10 newest
    except IndexError:
        entries = None                      # there are no entries

    before = 1                              # holder which tells us which page we're on

    cur = g.db.execute("""
        SELECT category
        FROM (
            SELECT category as category, count(category) as count
            FROM categories
            GROUP BY category
        )ORDER BY count DESC
    """)

    tags = [row for (row,) in cur.fetchall()]
    for element in ["None", "image", "album", "bookmark", "note"]:
        try:
            tags.remove(element)
        except ValueError:
            pass
    return render_template('blog_entries.html', entries=entries, before=before, popular_tags=tags[:10])


@app.route('/rss.xml')
def show_rss():
    """ The rss view: presents entries in rss form. """

    entries = []                            # store the entries which will be presented
    cur = g.db.execute(                     # grab in order of newest
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )

    for (row,) in cur.fetchall():           # iterate over the results
        if os.path.exists(row + ".json"):   # if the file fetched exists, append the parsed details
            entries.append(file_parser_json(row + ".json"))

    try:
        entries = entries[:10]              # get the 10 newest
    except IndexError:
        entries = None                      # there are no entries

    template = render_template('rss.xml', entries=entries)
    response = make_response(template)
    response.headers['Content-Type'] = 'application/xml'
    return response


@app.route('/json.feed')
def show_json():
    """ The rss view: presents entries in json feed form. """

    entries = []                            # store the entries which will be presented
    cur = g.db.execute(                     # grab in order of newest
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )

    for (row,) in cur.fetchall():           # iterate over the results
        if os.path.exists(row + ".json"):   # if the file fetched exists, append the parsed details
            entries.append(file_parser_json(row + ".json"))

    try:
        entries = entries[:10]              # get the 10 newest
    except IndexError:
        entries = None                      # there are no entries
    
    feed_items = []

    for entry in entries:
        feed_item = {
                        'id': entry['url'],
                        'url': entry['url'],
                        'content_text': entry['summary'] if entry['summary'] else entry['content'],
                        'date_published': entry['published'],
                        'author': {
                            'name': 'Alex Kearney'
                        }

                    }
        feed_items.append(feed_item)

    feed_json = {
        'version': 'https://jsonfeed.org/version/1',
        'home_page_url' : 'https://kongaloosh.com/',
        'feed_url' : 'https://kongaloosh.com/json.feed',
        'title' : 'kongaloosh',
        'items' : feed_items
    }
    
    return jsonify(feed_json)


@app.route('/page/<number>')
def pagination(number):
    """gets the posts for a page number"""
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        ORDER BY entries.published DESC
        """.format(datetime=datetime)
    )

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))

    try:
        start = int(number) * 10
        entries = entries[start:start + 10]
    except IndexError:
        entries = None

    before = int(number) + 1

    return render_template('blog_entries.html', entries=entries, before=before)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('page_not_found.html'), 404


@app.errorhandler(500)
def page_not_found(e):
    return render_template('server_error.html'), 500


def move_photos(text):

    file_path = "/mnt/volume-nyc1-01/images/temp/"  # todo: factor this out so that it's generalized

    file_path = "data/{0}/{1}/{2}/".format(
        date.year,
        date.month,
        date.day
    )

    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path))

    for uploaded_file in request.files.getlist('file'):
        uploaded_file.save(
            file_path + "{0}".format(
                uploaded_file.filename
            )
        )
        small_path = '/home/deploy/kongaloosh/data/'
        uploaded_file = open(file_path + '{0}'.format(uploaded_file.filename), 'r')


@app.route('/add', methods=['GET', 'POST'])
def add():
    """ The form for user-submission """
    if request.method == 'GET':
        cur = g.db.execute("""
               SELECT category
               FROM (
                   SELECT category as category, count(category) as count
                   FROM categories
                   GROUP BY category
               )ORDER BY count DESC
           """)

        tags = [row for (row,) in cur.fetchall()][:10]
        for element in ["None", "image", "album", "bookmark", "note"]:
            try:
                tags.remove(element)
            except ValueError:
                pass
        return render_template('add.html', popular_tags=tags)

    elif request.method == 'POST':  # if we're adding a new post
        if not session.get('logged_in'):
            abort(401)
        app.logger.info(request.form)

        data = post_from_request(request)

        if "Submit" in request.form:  # we're publishing it now; give it the present time
            data['published'] = datetime.now()

            data['content'] = run(data['content'], date=data['published'])

            if data['location'] is not None and data['location'].startswith("geo:"):
                if data['location'].startswith("geo:"):
                    app.logger.info(data['location'])
                    (place_name, geo_id) = resolve_placename(data['location'])
                    data['location_name'] = place_name
                    data['location_id'] = geo_id

            location = create_json_entry(data, g=g)

            if data['in_reply_to']:
                send_mention('http://' + DOMAIN_NAME + location, data['in_reply_to'])

            app.logger.info("posted at {0}".format(location))
            if request.form.get('twitter'):
                t = Timer(30, bridgy_twitter, [location])
                t.start()

            if request.form.get('facebook'):
                t = Timer(30, bridgy_facebook, [location])
                t.start()

        if "Save" in request.form:  # if we're simply saving the post as a draft
            location = create_json_entry(data, g=g, draft=True)

        return redirect(location)
    else:
        return redirect('/404'), 404


@app.route('/delete_draft/<name>', methods=['GET'])
def delete_drafts(year, month, day, name):
    app.logger.info("delete requested")
    if not session.get('logged_in'):
        abort(401)

    totalpath = "drafts/{name}"
    for extension in [".md", '.json', '.jpg']:
        if os.path.isfile(totalpath + extension):
            os.remove(totalpath + extension)
        return redirect('/', 200)


@app.route('/delete_entry/e/<year>/<month>/<day>/<name>', methods=['POST', 'GET'])
def delete_entry(year, month, day, name):
    app.logger.info(year)
    app.logger.info('here')
    app.logger.info("delete requested")
    app.logger.info(session.get('logged_in'))
    if not session.get('logged_in'):
        abort(401)
    else:
        totalpath = "data/{0}/{1}/{2}/{3}".format(year, month, day, name)
        for extension in [".md", '.json', '.jpg']:
            if os.path.isfile(totalpath + extension):
                os.remove(totalpath + extension)

        g.db.execute(
            """
            DELETE FROM ENTRIES
            WHERE Location=(?);
            """, (totalpath,)
        )
        g.db.commit()
        return redirect('/', 200)


@app.route('/bulk_upload', methods=['GET', 'POST'])
def bulk_upload():
    if request.method == 'GET':
        return render_template('bulk_photo_uploader.html')
    elif request.method == 'POST':
        if not session.get('logged_in'):
            abort(401)

        file_path = "/mnt/volume-nyc1-01/images/temp/"  # todo: factor this out so that it's generalized

        for uploaded_file in request.files.getlist('file'):
            uploaded_file.save(
                file_path + "{0}".format(
                    uploaded_file.filename
                )
            )
        return redirect('/')
    else:
        return redirect('/404'), 404


@app.route('/mobile_upload', methods=['GET', 'POST'])
def mobile_upload():
    if request.method == 'GET':
        return render_template('mobile_upload.html')
    elif request.method == 'POST':
        if not session.get('logged_in'):
            abort(401)

        file_path = "/mnt/volume-nyc1-01/images/temp/"  # todo: factor this out so that it's generalized
        app.logger.info("uploading at" + file_path)
        app.logger.info(request.files)
        app.logger.info(request.files.getlist('files[]'))
        for uploaded_file in request.files.getlist('files[]'):
            app.logger.info("file " + uploaded_file.filename)
            file_loc = file_path + "{0}".format(uploaded_file.filename)
            image = Image.open(uploaded_file)
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = dict(image._getexif().items())

            if exif[orientation] == 3:
                image = image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image = image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image = image.rotate(90, expand=True)
            image.save(file_loc)
        return redirect('/')
    else:
        return redirect('/404')


@app.route('/recent_uploads', methods=['GET', 'POST'])
def recent_uploads():
    """
    :returns a formatted list of all the images in the current day's directory
    """
    if request.method == 'GET':
        IMAGE_TEMPLATE = \
            '''
                <div class="row">
                    <div class="col-md-1 col-lg-1 col-sm-1">
                        <a class="fancybox" rel="group"  href="%s">
                            <img src="%s" class="img-responsive img-thumbnail" style="width:100">
                        </a>
                    </div>
                    <div class="col-md-11 col-lg-11 col-sm-11">
                        <a onclick="insertAtCaret('text_input','%s');return false;" >
                            <p style="font-size:8pt;">
                            %s
                            </p>
                        </a>
                    </div>
                </div>

            '''

        directory = "/mnt/volume-nyc1-01/images/temp"

        file_list = []
        for file in os.listdir(directory):
            path = ("/images/temp/" + file)
            file_list.append(path)

        preview = ""
        j = 0
        while True:
            row = ""
            for i in range(0, 4):  # for every row we want to make
                image_index = (4 * j) + i
                if image_index >= len(file_list):
                    preview += \
                        '''
                        <div class="row">
                            %s
                        </div>
                        ''' % (row)
                    return preview

                image_location = file_list[image_index]
                text_box_insert = "[](%s)" % image_location
                row += \
                    '''
                        <a onclick="insertAtCaret('text_input','%s');return false;">
                            <img src="%s" class="img-responsive img-thumbnail" style="max-width:%d%%; max-height:200px">
                        </a>
                    ''' % (text_box_insert, image_location, 100 / (4 + 0.2))
            preview += \
                '''
                <div class="row">
                    %s
                </div>
                ''' % (row)
            j += 1

        return preview
    else:
        return redirect('/404'), 404


def find_end_point(target):
    """Uses regular expressions to find a site's webmention endpoint"""
    html = requests.get(target)
    search_result = re.search('(rel(\ )*=(\ )*(")*webmention)(")*(.)*', html.content).group()
    url = re.search('((?<=href=)(\ )*(")*(.)*(")*)(?=/>)', search_result).group()
    url = re.sub('["\ ]', '', url)
    return url


def send_mention(source, target, endpoint=None):
    """Sends a webmention to a target site from our source link"""
    try:
        if not endpoint:
            endpoint = find_end_point(target)
        payload = {'source': source, 'target': target}
        headers = {'Accept': 'text/html, application/json'}
        app.logger.info(payload)
        r = requests.post(endpoint, data=payload, headers=headers)
        return r
    except:  # TODO: add a scope to the exception
        pass


def bridgy_facebook(location):
    """send a facebook mention to brid.gy"""
    # send the mention
    r = send_mention(
        'http://' + DOMAIN_NAME + location,
        'https://brid.gy/publish/facebook',
        endpoint='https://brid.gy/publish/webmention'
    )
    # get the response from the send
    syndication = r.json()
    data = file_parser_json('data/' + location.split('/e/')[1] + ".json", md=False)
    app.logger.info(syndication)
    if data['syndication']:
        data['syndication'].append(syndication['url'])
    else:
        data['syndication'] = [syndication['url']]
    data['facebook'] = {'url': syndication['url']}
    create_json_entry(data, g=None, update=True)


def bridgy_twitter(location):
    """send a twitter mention to brid.gy"""
    location = 'http://' + DOMAIN_NAME + location
    app.logger.info("bridgy sent to {0}".format(location))
    r = send_mention(
        location,
        'https://brid.gy/publish/twitter',
        endpoint='https://brid.gy/publish/webmention'
    )
    syndication = r.json()
    app.logger.info(syndication)
    app.logger.info("recieved {0} {1}".format(syndication['url'], syndication['id']))
    data = file_parser_json('data/' + location.split('/e/')[1] + ".json", md=False)
    if data['syndication']:
        data['syndication'].append(syndication['url'])
    else:
        data['syndication'] = [syndication['url']]
    data['twitter'] = {'url': syndication['url'],
                       'id': syndication['id']}
    create_json_entry(data, g=None, update=True)


def resolve_placename(location):
    try:
        (lat, long) = location[4:].split(',')
        try:
            float(long)
        except ValueError:
            long = re.search('(.)*(?=;)', long).group(0)
        geo_results = requests.get(
            'http://api.geonames.org/findNearbyPlaceNameJSON?style=Full&radius=5&lat=' + lat + '&lng=' + long + '&username=' + GEONAMES)
        place_name = geo_results.json()['geonames'][0]['name']
        if geo_results.json()['geonames'][0]['adminName2']:
            place_name += ", " + geo_results.json()['geonames'][0]['adminName2']
        elif geo_results.json()['geonames'][0]['adminName1']:
            place_name += ", " + geo_results.json()['geonames'][0]['adminName1']
        else:
            place_name += ", " + geo_results.json()['geonames'][0]['countryName']
        return place_name, geo_results.json()['geonames'][0]['geonameId']
    except IndexError:
        return None, None


def post_from_request(request):
    data = {
        'h': None,
        'title': None,
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

    for title in request.files:
        data[title] = request.files[title].read()

    for title in request.form:
        data[title] = request.form[title]

    for key in data:
        if data[key] == "None" or data[key] == '':
            data[key] = None

    return data


@app.route('/edit/e/<year>/<month>/<day>/<name>', methods=['GET', 'POST'])
def edit(year, month, day, name):
    """ The form for user-submission """
    if request.method == "GET":
        try:
            file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
            entry = file_parser_json(file_name + ".json", md=False)
            try:
                entry['category'] = ', '.join(entry['category'])
            except TypeError:
                entry['category'] = ''
            return render_template('edit_entry.html', entry=entry)
        except IOError:
            return redirect('/404')

    elif request.method == "POST":
        if not session.get('logged_in'):
            abort(401)
        app.logger.info("updating. {0}".format(request.form))

        if "Submit" in request.form:
            data = post_from_request(request)
            if data['location'] is not None and data['location'].startswith("geo:"):
                (place_name, geo_id) = resolve_placename(data['location'])
                data['location_name'] = place_name
                data['location_id'] = geo_id

            location = "{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)

            # data['content'] = run(data['content'], date=data['published'])

            if request.form.get('twitter'):
                t = Timer(30, bridgy_twitter, ['/e/' + location])
                t.start()

            if request.form.get('facebook'):
                t = Timer(30, bridgy_facebook, ['/e/' + location])
                t.start()

            file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
            entry = file_parser_json(file_name + ".json", g=g)
            update_json_entry(data, entry, g=g)
            return redirect("/e/" + location)
        return redirect("/")


@app.route('/e/<year>/<month>/<day>/<name>')
def profile(year, month, day, name):
    """ Get a specific article """

    file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
    if request.headers.get('Accept') == "application/ld+json":  # if someone else is consuming
        return action_stream_parser(file_name + ".json")

    entry = file_parser_json(file_name + ".json")

    # if os.path.exists(file_name + ".jpg"):
    #     entry['photo'] = file_name + ".jpg"  # get the actual file
    # if os.path.exists(file_name + ".mp4"):
    #     entry['video'] = file_name + ".mp4"  # get the actual file
    # if os.path.exists(file_name + ".mp3"):
    #     entry['audio'] = file_name + ".mp3"  # get the actual file

    mentions = get_mentions('http://' + DOMAIN_NAME + '/e/{year}/{month}/{day}/{name}'.
                            format(year=year, month=month, day=day, name=name))

    reply_to = []  # where we store our replies so we can fetch their info
    if entry['in_reply_to']:
        for i in entry['in_reply_to']:  # for all the replies we have...
            if type(i) == dict:  # which are not images on our site...
                reply_to.append(i)
            elif i.startswith('http://127.0.0.1:5000'):
                reply_to.append(file_parser_json(i.replace('http://127.0.0.1:5000/e/', 'data/', 1) + ".json"))
            elif i.startswith('http'):  # which are not data resources on our site...
                reply_to.append(get_entry_content(i))
    # if entry['syndication']:
    #     for i in entry['syndication'].split(','):               # look at all the syndication links
    #         if i.startswith('https://twitter.com/'):                    # if there's twitter syndication
    #             twitter = dict()
    #             vals = i.split('/')
    #             twitter['id'] = vals[len(vals)-1]
    #             twitter['link'] = i
    #             entry['twitter'] = twitter
    #         if i.startswith('https://www.facebook.com/'):
    #             entry['facebook'] = {'link':i}

    return render_template('entry.html', entry=entry, mentions=mentions, reply_to=reply_to)


@app.route('/t/<category>')
def tag_search(category):
    """ Get all entries with a specific tag """
    entries = []
    cur = g.db.execute(
        """
         SELECT entries.location FROM categories
         INNER JOIN entries ON
         entries.slug = categories.slug AND
         entries.published = categories.published
         WHERE categories.category='{category}'
         ORDER BY entries.published DESC
        """.format(category=category))
    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))
    return render_template('blog_entries.html', entries=entries)


@app.route('/e/<year>/')
def time_search_year(year):
    """ Gets all entries posted during a specific year """
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        WHERE CAST(strftime('%Y',entries.published)AS INT) = {year}
        ORDER BY entries.published DESC
        """.format(year=int(year)))

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))
    return render_template('blog_entries.html', entries=entries)


@app.route('/e/<year>/<month>/')
def time_search_month(year, month):
    """ Gets all entries posted during a specific month """
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        WHERE CAST(strftime('%Y',entries.published)AS INT) = {year}
        AND CAST(strftime('%m',entries.published)AS INT) = {month}
        ORDER BY entries.published DESC
        """.format(year=int(year), month=int(month)))

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))
    return render_template('blog_entries.html', entries=entries)


@app.route('/e/<year>/<month>/<day>/')
def time_search(year, month, day):
    """ Gets all notes posted on a specific day """
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        WHERE CAST(strftime('%Y',entries.published)AS INT) = {year}
        AND CAST(strftime('%m',entries.published)AS INT) = {month}
        AND CAST(strftime('%d',entries.published)AS INT) = {day}
        ORDER BY entries.published DESC
        """.format(year=int(year), month=int(month), day=int(day)))

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))
    return render_template('blog_entries.html', entries=entries)


@app.route('/a/')
def articles():
    """ Gets all the articles """
    entries = []
    cur = g.db.execute(
        """
         SELECT entries.location FROM categories
         INNER JOIN entries ON
         entries.slug = categories.slug AND
         entries.published = categories.published
         WHERE categories.category='{category}'
         ORDER BY entries.published DESC
        """.format(category='article'))

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))
    return render_template('blog_entries.html', entries=entries)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            return redirect('/add')
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))


# TODO: the POST functionality could 100% just be the same as our add function
@app.route('/micropub', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def handle_micropub():
    app.logger.info('handleMicroPub [%s]' % request.method)
    if request.method == 'POST':  # if post, authorise and create
        access_token = request.headers.get('Authorization')  # get the token and report it
        app.logger.info('token [%s]' % access_token)
        if access_token:  # if the token is not none...
            access_token = access_token.replace('Bearer ', '')
            app.logger.info('acccess [%s]' % request)
            if checkAccessToken(access_token, request.form.get("client_id.data")):  # if the token is valid ...
                app.logger.info('authed')
                app.logger.info(request.data)
                app.logger.info(request.files)
                data = {
                    'h': None,
                    'title': None,
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

                for key in (
                        'name', 'summary', 'content', 'published', 'updated', 'category',
                        'slug', 'location', 'place_name', 'in_reply_to', 'repost-of', 'syndication', 'syndicate-to[]'):
                    try:
                        data[key] = request.form.get(key)
                    except KeyError:
                        pass

                if type(data['category']) == unicode:
                    data['category'] = [i.strip() for i in data['category'].lower().split(",")]


                if not data['published']:  # if we don't have a timestamp, make one now
                    data['published'] = datetime.today()
                else:
                    data['published'] = parse(data['published'])


                for key, name in [('photo', 'image'), ('audio', 'audio'), ('video', 'video')]:
                    try:
                        if request.files.get(key):
                            img = request.files.get(key)
                            data[key] = img
                            data['category'].append(name)  # we've added an image, so append it
                    except KeyError:
                        pass

                if data['location'] is not None and data['location'].startswith("geo:"):
                    if data['place_name']:
                        data['location_name'] = data['place_name']
                    elif data['location'].startswith("geo:"):
                        (place_name, geo_id) = resolve_placename(data['location'])
                        data['location_name'] = place_name
                        data['location_id'] = geo_id

                location = create_json_entry(data, g=g)

                if data['in_reply_to']:
                    send_mention('http://' + DOMAIN_NAME + location, data['in_reply_to'])

                # regardless of whether or not syndication is called for, if there's a photo, send it to FB and twitter
                try:
                    if request.form.get('twitter') or data['photo']:
                        t = Timer(30, bridgy_twitter, [location])
                        t.start()
                except KeyError:
                    pass
                try:
                    if request.form.get('facebook') or data['photo']:
                        t = Timer(30, bridgy_facebook, [location])
                        t.start()
                except KeyError:
                    pass

                resp = Response(status="created", headers={'Location': 'http://' + DOMAIN_NAME + location})
                resp.status_code = 201
                return resp
            else:
                resp = Response(status='unauthorized')
                resp.status_code = 401
                return resp
        else:    
            resp = Response(status='unauthorized')
            resp.status_code = 401

    elif request.method == 'GET':
        qs = request.query_string
        if request.args.get('q') == 'syndicate-to':
            syndicate_to = [
                'twitter.com/',
                'tumblr.com/',
                'facebook.com/'
            ]

            r = ''
            while len(syndicate_to) > 1:
                r += 'syndicate-to[]=' + syndicate_to.pop() + '&'
            r += 'syndicate-to[]=' + syndicate_to.pop()
            resp = Response(content_type='application/x-www-form-urlencoded', response=r)
            return resp
        resp = Response(status='not implemented')
        resp.status_code = 501
        return resp


@app.route('/inbox', methods=['GET', 'POST', 'OPTIONS'])
def handle_inbox():
    app.logger.info(request)
    if request.method == 'GET':
        inbox_location = "inbox/"
        entries = [
            f for f in os.listdir(inbox_location)
            if os.path.isfile(os.path.join(inbox_location, f))
            and f.endswith('.json')]

        for_approval = [entry for entry in entries if entry.startswith("approval_")]
        entries = [entry for entry in entries if not entry.startswith("approval_")]
        if 'text/html' in request.headers.get('Accept'):
            return render_template('inbox.html', entries=entries, for_approval=for_approval)
        elif 'application/ld+json' in request.headers.get('Accept'):
            inbox_items = {}
            inbox_items['@context'] = "https://www.w3.org/ns/ldp"
            inbox_items['@id'] = "http://" + DOMAIN_NAME + "/inbox"
            inbox_items['http://www.w3.org/ns/ldp#contains'] = [{"@id": "http://" + DOMAIN_NAME + "/inbox/" + entry} for entry in entries]
            resp = Response(inbox_items, content_type="application/ld+json", status=200)
            resp.data = json.dumps(inbox_items)
            return resp
        # else:
        #     resp = Response(content_type="application/ld+json", status=200)
        #     resp.data = """
        #         <inbox>
        #         a ldp:Container
        #         ldp:contains {0}
        #         </inbox>
        #         """.format([{"@id": "http://" + DOMAIN_NAME + "/inbox/" + entry} for entry in entries])
        #     return resp
        else:
            resp = Response(status=501)
            return resp
    elif request.method == 'POST':
        data = json.loads(request.data)
        try:
            sender = data['actor']['@id']
        except TypeError:
            sender = data['actor']
        except KeyError:
            try:
                sender = data['actor']['id']
            except KeyError:
                sender = None

        if sender == 'https://rhiaro.co.uk' or sender == "https://rhiaro.co.uk/#me":  # check if the sender is whitelisted
            # todo: make better names for notifications
            app.logger.info("it's Rhiaro!")
            location = 'inbox/' + slugify(str(datetime.now())) + '.json'
            notification = open(location, 'w+')
            notification.write(request.data)
            resp = Response(status=201, headers={'Location':location})
            return resp
        else:  # if the sender isn't whitelisted
            try:
                try:
                    data['context']
                    notification = open('inbox/approval_' + slugify(str(datetime.now())) + '.json', 'w+')
                    notification.write(request.data)
                    resp = Response(status='queued')
                    resp.data = {"@id": "", "http://www.w3.org/ns/ldp#contains": []}
                    resp.status_code = 202
                    return resp
                except KeyError:
                    resp = Response(403)
                    resp.status_code = 403
                    return resp
            except requests.ConnectionError:
                resp = Response(status='unauthorized')
                resp.status_code = 403
                return resp
    else:
        resp = Response(status='Not Implemented')
        resp.status_code = 501
        app.logger.info(resp)
        return resp


@app.route('/inbox/send/', methods=['GET', 'POST'])
def notifier():
    return 501

@app.route('/inbox/<name>', methods=['GET'])
def show_inbox_item(name):
    if request.method == 'GET':
        entry = json.loads(open('inbox/' + name).read())
        app.logger.info((request, request.data))
        try:
            if request.headers.get('Accept') == "application/ld+json":  # if someone else is consuming
                inbox_items = {}
                resp = Response(content_type="application/ld+json", status=200)
                resp.data = json.dumps(entry)
                return resp

            if 'text/html' in request.headers.get('Accept'):
                try:
                    sender = entry['actor']['@id']
                except KeyError:
                    try:
                        sender = entry['actor']['id']
                    except KeyError:
                        sender = entry['@id']
                except TypeError:
                    sender = entry['actor']
                return render_template('inbox_notification.html', entry=entry, sender=sender)

            else:
                # app.logger.info(request.headers.get('Accept'))
                # resp = Response(content_type="application/ld+json", status=200)
                # resp.data = """
                #     <inbox>
                #     a ldp:Container
                #     ldp:contains {0}
                #     </inbox>
                #     """.format(str(entry))
                inbox_items = {}
                resp = Response(content_type="application/ld+json", status=200)
                resp.data = json.dumps(entry)
            return resp

        except TypeError:
            # app.logger.info("empyt")
            # resp = Response(content_type="application/ld+json", status=200)
            # resp.data = """
            #     <inbox>
            #     a ldp:Container
            #     ldp:contains {0}
            #     </inbox>
            #     """.format(str(entry))
            # return resp
                inbox_items = {}
                resp = Response(content_type="application/ld+json", status=200)
                resp.data = json.dumps(entry)
                return resp


@app.route('/drafts', methods=['GET'])
def show_drafts():
    if request.method == 'GET':
        drafts_location = "drafts/"
        entries = [
            drafts_location + f for f in os.listdir(drafts_location)
            if os.path.isfile(os.path.join(drafts_location, f))
            and f.endswith('.json')]
        entries = [file_parser_json(entry) for entry in entries]
        return render_template("drafts_list.html", entries=entries)


@app.route('/drafts/<name>', methods=['GET', 'POST'])
def show_draft(name):
    if request.method == 'GET':
        draft_location = 'drafts/' + name + ".json"
        entry = file_parser_json(draft_location, md=False)
        if entry['category']:
            entry['category'] = ', '.join(entry['category'])
        return render_template('edit_draft.html', entry=entry)

    if request.method == 'POST':
        if not session.get('logged_in'):
            abort(401)
        data = post_from_request(request)

        if "Save" in request.form:  # if we're updating a draft
            file_name = "drafts/{0}".format(name)
            entry = file_parser_json(file_name + ".json")
            location = update_json_entry(data, entry, g=g, draft=True)
            return redirect("/drafts")

        if "Submit" in request.form:  # if we're publishing it now
            data['published'] = datetime.now()

            location = create_json_entry(data, g=g)
            if data['in_reply_to']:
                send_mention('http://' + DOMAIN_NAME + location, data['in_reply_to'])

            if request.form.get('twitter'):
                t = Timer(30, bridgy_twitter, [location])
                t.start()

            if request.form.get('facebook'):
                t = Timer(30, bridgy_facebook, [location])
                t.start()

            if os.path.isfile("drafts/" + name + ".json"):  # this won't always be the slug generated
                os.remove("drafts/" + name + ".json")

            return redirect(location)


@app.route('/notification', methods=['GET', 'POST'])
def notification():
    pass


@app.route('/already_made', methods=['GET'])
def post_already_exists():
    return render_template('already_exists.html')


if __name__ == "__main__":
    app.run(debug=True)
