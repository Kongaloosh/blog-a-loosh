#!/usr/bin/python
# coding: utf-8
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
    render_template, flash, Response, send_file
from contextlib import closing
import os
import math
from datetime import datetime
from jinja2 import Environment
from dateutil.parser import parse
from pysrc.webmention.extractor import get_entry_content
from pysrc.posse_scripts import tweeter
from pysrc.file_management.file_parser import editEntry, create_entry, file_parser, get_bare_file, entry_re_write, activity_stream_parser
from pysrc.authentication.indieauth import checkAccessToken
from pysrc.webmention.webemention_checking import get_mentions
from pysrc.webmention.mentioner import send_mention
from rdflib import Graph, plugin
import pickle
from threading import Timer
import requests
import json
from slugify import slugify

jinja_env = Environment(extensions=['jinja2.ext.with_'])

# configuration
DATABASE = 'kongaloosh.db'
DEBUG = True
SECRET_KEY = open('config/development_key', 'rb').read().rstrip('\n')
USERNAME = open('config/site_authentication/username', 'rb').read().rstrip('\n')
PASSWORD = open('config/site_authentication/password', 'rb').read().rstrip('\n')
DOMAIN_NAME = open('config/domain_name', 'rb').read().rstrip('\n')
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
    entries = []
    cur = g.db.execute(
        "SELECT location "
        +"FROM entries "
        +"ORDER BY published DESC")
    for (row,) in cur.fetchall():
        if os.path.exists(row+".md"):
            entries.append(file_parser(row+".md"))
    try:
        entries=entries[:10]
    except IndexError:
        entries=None

    before = 1

    for entry in entries:
        for i in entry['syndication'].split(','):
            if i.startswith('https://twitter.com/'):
                twitter = dict()
                vals = i.split('/')
                twitter['id'] = vals[len(vals)-1]
                twitter['link'] = i
                entry['twitter'] = twitter
                break

    return render_template('blog_entries.html', entries=entries, before=before)


@app.route('/page/<number>')
def pagination(number):
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        ORDER BY entries.published DESC
        """.format(datetime=datetime)
    )

    for (row,) in cur.fetchall():
        if os.path.exists(row+".md"):
            entries.append(file_parser(row+".md"))

    try:
        start = int(number) * 10
        entries = entries[start:start+10]
    except IndexError:
        entries = None

    before = int(number)+1

    return render_template('blog_entries.html', entries=entries, before=before)


@app.route('/404')
def four_oh_four():
    return render_template('page_not_found.html'), 404


@app.route('/stream')
def show_entries_stream():
    """ A simple stream that people can go to if they don't want the cover """
    pass


@app.route('/add', methods=['GET', 'POST'])
def add():
    """ The form for user-submission """
    if request.method == 'GET':
        return render_template('add.html')

    elif request.method == 'POST':              # if we're adding a new post
        app.logger.info(request.form)
        if "Submit" in request.form:            # if we're publishing it now
            data = {}
            for key in ('h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                        'slug', 'location', 'in-reply-to', 'repost-of', 'syndication'):
                data[key] = None

            for title in request.form:
                data[title] = request.form[title]

            for title in request.files:
                data[title] = request.files[title].read()

            try:
                data['photo'] = request.files['photo']
            except KeyError:
                data['photo'] = None

            for key in data:
                if data[key] == "":
                    data[key] = None

            data['published'] = datetime.now()

            location = create_entry(data, image=data['photo'], g=g)

            if data['in-reply-to']:
                send_mention('http://' + DOMAIN_NAME + '/e/'+location, data['in-reply-to'])

            if request.form.get('twitter'):
                t = Timer(30, bridgy_twitter, [location])
                t.start()

            if request.form.get('facebook'):
                t = Timer(30, bridgy_facebook, [location])
                t.start()

        if "Save" in request.form:
            data = {}
            for key in ('h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                        'slug', 'location', 'in-reply-to', 'repost-of', 'syndication'):
                data[key] = None

            for title in request.form:
                data[title] = request.form[title]

            for title in request.files:
                data[title] = request.files[title].read()

            try:
                photo = request.files['photo']
            except KeyError:
                photo = None

            for key in data:
                if data[key] == "":
                    data[key] = None

            location = create_entry(data, image=data['photo'], g=g, draft=True)

        return redirect(location)
    else:
        return redirect('/404'), 404


@app.route('/bulk_upload', methods=['GET', 'POST'])
def bulk_upload():
    if request.method == 'GET':
        return render_template('bulk_photo_uploader.html')
    elif request.method == 'POST':
        date = datetime.now()

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
        return redirect('/')
    else:
        return redirect('/404'), 404


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

        now = datetime.now()
        directory = "data/{0}/{1}/{2}".format(now.year, now.month, now.day)

        file_list = []
        for file in os.listdir(directory):
            if file.endswith((".jpg", ".png", ".gif")):
                path = (directory + "/" + file)
                file_list.append(path)

        preview = ""
        j = 0
        while (True):
            row = ""
            for i in range(0,4):            # for every row we want to make
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
                    ''' % (text_box_insert, image_location, 100/(4+0.2))
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


def bridgy_facebook(location):
    """send a facebook mention to brid.gy"""
    r = send_mention(
        'http://' + DOMAIN_NAME + '/e/' + location,
        'https://brid.gy/publish/facebook',
        endpoint='https://brid.gy/publish/webmention'
    )
    syndication = r.json()
    data = get_bare_file('data/' + location.split('/e/')[1]+".md")
    if data['syndication'] == 'None':
        data['syndication'] = syndication['url']+","
    else:
        data['syndication'] += syndication['url']+","
    entry_re_write(data)


def bridgy_twitter(location):
    """send a twitter mention to brid.gy"""
    r = send_mention(
        'http://' + DOMAIN_NAME +'/e/' + location,
        'https://brid.gy/publish/twitter',
        endpoint='https://brid.gy/publish/webmention'
    )
    location = 'http://' + DOMAIN_NAME +'/e/' + location
    syndication = r.json()
    app.logger.info(syndication)
    data = get_bare_file('data/' + location.split('/e/')[1]+".md")
    if data['syndication'] == 'None':
        data['syndication'] = syndication['url']+","
    else:
        data['syndication'] += syndication['url']+","
    entry_re_write(data)


@app.route('/edit/<year>/<month>/<day>/<name>', methods=['GET','POST'])
def edit(year, month, day, name):
    """ The form for user-submission """
    if request.method == "GET":
        try:
            file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
            entry = get_bare_file(file_name+".md")
            return render_template('edit_entry.html', entry=entry)
        except:
            return render_template('page_not_found.html')

    elif request.method == "POST":
        data = {}
        app.logger.info(request.form)

        if "Submit" in request.form:
            for key in ('h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                        'slug', 'location', 'in-reply-to', 'repost-of', 'syndication'):
                data[key] = None

            for title in request.form:
                data[title] = request.form[title]

            for title in request.files:
                data[title] = request.files[title].read()

            for key in data:
                if data[key] == "":
                    data[key] = None

            location = "{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)

            if request.form.get('twitter'):
                t = Timer(30, bridgy_twitter, [location])
                t.start()

            if request.form.get('facebook'):
                t = Timer(30, bridgy_facebook, [location])
                t.start()
            file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
            entry = get_bare_file(file_name+".md")

            location = editEntry(data, old_entry=entry, g=g)
            return redirect(location)
        return redirect("/")


@app.route('/data/<year>/<month>/<day>/image/<name>')
def image_fetcher_depricated(year, month, day, name):
    """ do not use---old image fetcher """
    entry = 'data/{year}/{month}/{day}/image/{name}'.format(year=year, month=month, day=day, type=type, name=name)
    img = open(entry)
    return send_file(img)


@app.route('/data/<year>/<month>/<day>/<name>')
def image_fetcher(year, month, day, name):
    """ Retruns a specific image """
    entry = 'data/{year}/{month}/{day}/{name}'.format(year=year, month=month, day=day, type=type, name=name)
    img = open(entry)
    return send_file(img)


@app.route('/e/<year>/<month>/<day>/<name>')
def profile(year, month, day, name):
    """ Get a specific article """

    file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
    if request.headers.get('Accept') == "application/ld+json":  # if someone else is consuming
        return action_stream_parser(file_name+".md")

    entry = file_parser(file_name+".md")

    if os.path.exists(file_name+".jpg"):
        entry['photo'] = file_name+".jpg" # get the actual file
    if os.path.exists(file_name+".mp4"):
        entry['video'] = file_name+".mp4" # get the actual file
    if os.path.exists(file_name+".mp3"):
        entry['audio'] = file_name+".mp3" # get the actual file

    mentions = get_mentions('http://' + DOMAIN_NAME + '/e/{year}/{month}/{day}/{name}'.
                            format(year=year, month=month, day=day, name=name))

    reply_to = []                                           # where we store our replies so we can fetch their info
    for i in entry['in_reply_to']:                          # for all the replies we have...
        if type(i) == dict:           # which are not images on our site...
            reply_to.append(i)
        elif i.startswith('http://127.0.0.1:5000'):
            reply_to.append(file_parser(i.replace('http://127.0.0.1:5000/e/', 'data/', 1) + ".md"))
        elif i.startswith('http'):                          # which are not data resources on our site...
            reply_to.append(get_entry_content(i))

    for i in entry['syndication'].split(','):
        if i.startswith('https://twitter.com/'):                    # if there's twitter syndication
            twitter = dict()
            vals = i.split('/')
            twitter['id'] = vals[len(vals)-1]
            twitter['link'] = i
            entry['twitter'] = twitter
        if i.startswith('https://www.facebook.com/'):
            entry['facebook'] = {'link':i}

    return render_template('entry.html', entry=entry, mentions=mentions, reply_to=reply_to)
    # except:
    #     return redirect('/404'), 404


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
        if os.path.exists(row+".md"):
            entries.append(file_parser(row+".md"))
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
        if os.path.exists(row+".md"):
            entries.append(file_parser(row+".md"))
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
        if os.path.exists(row+".md"):
            entries.append(file_parser(row+".md"))
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
        if os.path.exists(row+".md"):
            entries.append(file_parser(row+".md"))
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
        if os.path.exists(row+".md"):
            entries.append(file_parser(row+".md"))
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


@app.route('/micropub', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def handle_micropub():
    app.logger.info('handleMicroPub [%s]' % request.method)
    if request.method == 'POST':                                                    # if post, authorise and create
        access_token = request.headers.get('Authorization')                         # get the token and report it
        app.logger.info('token [%s]' % access_token)
        if access_token:                                                            # if the token is not none...
            access_token = access_token.replace('Bearer ', '')
            app.logger.info('acccess [%s]' % request)
            if checkAccessToken(access_token, request.form.get("client_id.data")):  # if the token is valid ...
                app.logger.info('authed')
                data = {}

                for key in (
                        'h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                        'slug', 'location', 'in-reply-to', 'repost-of', 'syndication', 'syndicate-to[]'):
                    data[key] = request.form.get(key)

                if data['syndication']:
                    data['syndication'] += ","

                if not data['published']:                       # if we don't have a timestamp, make one now
                    data['published'] = datetime.today()
                else:
                    data['published'] = parse(data['published'])

                if request.files.get('photo'):
                    img = request.files.get('photo').read()
                    data['photo'] = img
                    data['category'] += ',image'                # we've added an image, so append it
                else:
                    data['photo'] = None

                try:
                    audio = request.files.get('audio').read()
                    data['audio'] = audio
                    data['category'] += ',audio'                # we've added an image, so append it
                except: pass

                try:
                    video = request.files.get('video').read()
                    data['video'] = video
                    data['category'] += ',video'                # we've added an image, so append it
                except: pass

                location = create_entry(data, image=data['photo'], g=g)
                
                # regardless of whether or not syndication is called for, if there's a photo, send it to FB and twitter
                if request.form.get('twitter') or data['photo']:
                    t = Timer(10, bridgy_twitter, [location])
                    t.start()

                if request.form.get('facebook') or data['photo']:
                    t = Timer(20, bridgy_facebook, [location])
                    t.start()

                resp = Response(status="created", headers={'Location': 'http://' + DOMAIN_NAME + location})
                resp.status_code = 201
                return resp
            else:
                return 'unauthorized', 403
        else:
            return 'unauthorized', 401

    elif request.method == 'GET':
        qs = request.query_string
        if request.args.get('q') == 'syndicate-to':
            syndicate_to = [
                'twitter.com/',
                'tumblr.com/',
            ]
            r = ''
            while len(syndicate_to) > 1:
                r += 'syndicate-to[]=' + syndicate_to.pop() + '&'
            r += 'syndicate-to[]=' + syndicate_to.pop()
            resp = Response(content_type='application/x-www-form-urlencoded', response=r)
            return resp
        return 'not implemented', 501


@app.route('/inbox', methods=['GET', 'POST'])
def handle_inbox():
    if request.method == 'GET':
        inbox_location = "inbox/"
        entries = [
            f for f in os.listdir(inbox_location)
            if os.path.isfile(os.path.join(inbox_location, f))
            and f.endswith('.json')]

        for_approval = [entry for entry in entries if entry.startswith("approval_")]
        entries = [entry for entry in entries if not entry.startswith("approval_")]

        if request.headers.get('Accept') == "application/ld+json":  # if someone else is consuming
            inbox_items = {}
            inbox_items['@context'] = "https://www.w3.org/ns/ldp"
            inbox_items['@id'] = "http://" + DOMAIN_NAME + "/inbox"
            inbox_items['contains'] = [{"@id": "http://" + DOMAIN_NAME + "/inbox/" + entry} for entry in entries]
            return json.dumps(inbox_items)

        return render_template('inbox.html', entries=entries, for_approval=for_approval)

    elif request.method == 'POST':
        # check content is json-ld

            data = json.loads(request.data)
            app.logger.info(data)
            try:
                sender = data['actor']['@id']
            except KeyError:
                try:
                    sender = data['actor']['id']
                except KeyError:
                    return "could not validate notification sender: no actor id", 403

            if sender == 'https://rhiaro.co.uk':             # check if the sender is whitelisted
                # todo: make better names for notifications
                notification = open('inbox/' + slugify(str(datetime.now())) + '.json','w+')
                notification.write(request.data)
                return "added to inbox", 202
            else:                                           # if the sender isn't whitelisted
                try:
                    validate = requests.get(sender)
                    if validate.status_code - 200 < 100:    # if the sender is real
                        notification = open('inbox/approval_' + slugify(str(datetime.now())) + '.json','w+')
                        notification.write(request.data)
                        return "queued", 202
                    else:
                        return "forbidden", 403
                except requests.ConnectionError:
                    return "forbidden", 403
    else:
        return "this is not implemented", 501


@app.route('/inbox/send/', methods=['GET', 'POST'])
def notifier():
    return 501


@app.route('/inbox/<name>', methods=['GET'])
def show_inbox_item(name):
    if request.method == 'GET':
        entry = json.loads(open('inbox/'+name).read())

        if request.headers.get('Accept') == "application/ld+json":  # if someone else is consuming
            return json.dumps(entry)

        try:
            sender = entry['actor']['@id']
        except KeyError:
            sender = entry['actor']['id']

        return render_template('inbox_notification.html', entry=entry, sender=sender)


@app.route('/drafts', methods=['GET'])
def show_drafts():
    if request.method == 'GET':
        drafts_location = "drafts/"
        entries = [
                drafts_location + f for f in os.listdir(drafts_location)
                if os.path.isfile(os.path.join(drafts_location, f))
                and f.endswith('.md')]
        entries = [get_bare_file(entry) for entry in entries]
        return render_template("drafts_list.html", entries=entries)

@app.route('/drafts/<name>', methods=['GET','POST'])
def show_draft(name):
    if request.method == 'GET':
        draft_location = 'drafts/' + name + ".md"
        entry = get_bare_file(draft_location)
        return render_template('edit_draft.html', entry=entry)
    if request.method == 'POST':
        data = {}
        if "Save" in request.form:
            for key in ('h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                        'slug', 'location', 'in-reply-to', 'repost-of', 'syndication'):
                data[key] = None

            for title in request.form:
                data[title] = request.form[title]

            for title in request.files:
                data[title] = request.files[title].read()

            file_name = "drafts/{0}".format(name)
            entry = get_bare_file(file_name+".md")
            location = editEntry(data, old_entry=entry, g=g)
            return redirect("/drafts")
        if "Submit" in request.form:            # if we're publishing it now
            data = {}
            for key in ('h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                        'slug', 'location', 'in-reply-to', 'repost-of', 'syndication'):
                data[key] = None
            for title in request.form:
                if request.form[title] is not 'None':
                    data[title] = request.form[title]

            for key in data.keys():
                if data[key] == "None":
                    data[key] = None

            for title in request.files:
                data[title] = request.files[title].read()

            try:
                data['photo'] = request.files['photo']
            except KeyError:
                data['photo'] = None

            data['published'] = datetime.now()

            location = create_entry(data, image=data['photo'], g=g)
            if data['in-reply-to']:
                send_mention('http://' + DOMAIN_NAME + '/e'+location, data['in-reply-to'])

            if request.form.get('twitter'):
                t = Timer(30, bridgy_twitter, [location])
                t.start()

            if request.form.get('facebook'):
                t = Timer(30, bridgy_facebook, [location])
                t.start()

            if os.path.isfile("drafts/"+name+".md"): # this won't always be the slug generated
                os.remove("drafts/"+name+".md")

            return redirect(location)


@app.route('/notification', methods=['GET','POST'])
def notification():
    pass


if __name__ == "__main__":
    app.run(debug=True)
