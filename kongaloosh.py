#!/usr/bin/python
# coding: utf-8
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
    render_template, flash, Response, send_file
from contextlib import closing
import os
from datetime import datetime
from jinja2 import Environment
import ronkyuu
import ninka
from mf2py.parser import Parser
from dateutil.parser import parse
import requests

from pysrc.posse_scripts import tweeter
from pysrc.file_management.file_parser import editEntry, createEntry, file_parser, get_bare_file
jinja_env = Environment(extensions=['jinja2.ext.with_'])

# configuration
DATABASE = 'kongaloosh.db'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'Anubis'
PASSWORD = 'Munc4kin))'
# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config['STATIC_FOLDER'] = os.getcwd()
cfg = None

""" DATABASE """
def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


""" WEBMENTION """
def processWebmention(sourceURL, targetURL, vouchDomain=None):
    result = False
    r = requests.get(sourceURL, verify=False)
    if r.status_code == requests.codes.ok:
        mentionData = { 'sourceURL':   sourceURL,
                        'targetURL':   targetURL,
                        'vouchDomain': vouchDomain,
                        'vouched':     False,
                        'received':    datetime.date.today().strftime('%d %b %Y %H:%M'),
                        'postDate':    datetime.date.today().strftime('%Y-%m-%dT%H:%M:%S')
                        }
        if 'charset' in r.headers.get('content-type', ''):
            mentionData['content'] = r.text
        else:
            mentionData['content'] = r.content
        if vouchDomain is not None and cfg['require_vouch']:
            mentionData['vouched'] = processVouch(sourceURL, targetURL, vouchDomain)
            result                 = mentionData['vouched']
            app.logger.info('result of vouch? %s' % result)
        else:
            result = not cfg['require_vouch']
            app.logger.info('no vouch domain, result %s' % result)

        mf2Data = Parser(doc=mentionData['content']).to_dict()
        hcard   = extractHCard(mf2Data)
        mentionData['hcardName'] = hcard['name']
        mentionData['hcardURL']  = hcard['url']
        mentionData['mf2data']   = mf2Data

        # Do something with the inbound mention

    return result


def mention(sourceURL, targetURL, vouchDomain=None):
    """Process the Webmention of the targetURL from the sourceURL.

    To verify that the sourceURL has indeed referenced our targetURL
    we run findMentions() at it and scan the resulting href list.
    """
    app.logger.info('discovering Webmention endpoint for %s' % sourceURL)

    mentions = ronkyuu.findMentions(sourceURL)
    result   = False
    app.logger.info('mentions %s' % mentions)
    for href in mentions['refs']:
        if href != sourceURL and href == targetURL:
            app.logger.info('post at %s was referenced by %s' % (targetURL, sourceURL))

            result = processWebmention(sourceURL, targetURL, vouchDomain)
    app.logger.info('mention() returning %s' % result)
    return result


def extractHCard(mf2Data):
    result = { 'name': '',
               'url':  '',
               }
    if 'items' in mf2Data:
        for item in mf2Data['items']:
            if 'type' in item and 'h-card' in item['type']:
                result['name'] = item['properties']['name']
                if 'url' in item['properties']:
                    result['url'] = item['properties']['url']
    return result


def processVouch(sourceURL, targetURL, vouchDomain):
    """Determine if a vouch domain is valid.

    This implements a very simple method for determining if a vouch should
    be considered valid:
    1. does the vouch domain have it's own webmention endpoint
    2. does the vouch domain have an indieauth endpoint
    3. does the domain exist in the list of domains i've linked to

    yep, super simple but enough for me to test implement vouches
    """
    vouchFile = os.path.join(cfg['basepath'], 'vouch_domains.txt')
    with open(vouchFile, 'r') as h:
        vouchDomains = []
        for domain in h.read():
            vouchDomains.append(domain.strip().lower())

    if vouchDomain.lower() in vouchDomains:
        result = True
    else:
        wmStatus, wmUrl = ronkyuu.discoverEndpoint(vouchDomain, test_urls=False)
        if wmUrl is not None and wmStatus == 200:
            authEndpoints = ninka.indieauth.discoverAuthEndpoints(vouchDomain)

            if 'authorization_endpoint' in authEndpoints:
                authURL = None
                for url in authEndpoints['authorization_endpoint']:
                    authURL = url
                    break
                if authURL is not None:
                    result = True
                    with open(vouchFile, 'a+') as h:
                        h.write('\n%s' % vouchDomain)


""" AUTHENTICATION"""
def checkAccessToken(access_token, client_id):
    """
    code=gk7n4opsyuUxhvF4&
    redirect_uri=https://example.com/auth&
    client_id=https://example.com/
    """
    r = requests.get(url='https://tokens.indieauth.com/token', headers={'Authorization': 'Bearer '+access_token})
    return r.status_code == requests.codes.ok


""" MICROPUB """

def processWebmention(sourceURL, targetURL, vouchDomain=None):
    result = False
    r = requests.get(sourceURL, verify=False)
    if r.status_code == requests.codes.ok:
        mentionData = { '7.0.0.1/sourceURL':   sourceURL,
                        'targetURL':   targetURL,
                        'vouchDomain': vouchDomain,
                        'vouched':     False,
                        'received':    datetime.date.today().strftime('%d %b %Y %H:%M'),
                        'postDate':    datetime.date.today().strftime('%Y-%m-%dT%H:%M:%S')
                        }
        if 'charset' in r.headers.get('content-type', ''):
            mentionData['content'] = r.text
        else:
            mentionData['content'] = r.content

        if vouchDomain is not None and cfg['require_vouch']:
            mentionData['vouched'] = processVouch(sourceURL, targetURL, vouchDomain)
            result = mentionData['vouched']
            app.logger.info('result of vouch? %s' % result)
        else:
            result = not cfg['require_vouch']
            app.logger.info('no vouch domain, result %s' % result)

        mf2Data = Parser(doc=mentionData['content']).to_dict()
        hcard = extractHCard(mf2Data)

        mentionData['hcardName'] = hcard['name']
        mentionData['hcardURL']  = hcard['url']
        mentionData['mf2data']   = mf2Data

        # Do something with the inbound mention
        g.db.execute('insert into mentions (content_text, source_url, target_url, post_date) values (?, ?, ?, ?)',
                     [mentionData['content'], mentionData['sourceURL'], mentionData['targetURL'], mentionData['postDate']])
        g.db.commit()


def validURL(targetURL):
    """
        Validate the target URL exists.
        In a real app you would need to do a database lookup or a HEAD request, here we just check the URL
    """
    if '/article' in targetURL:
        result = 200
    else:
        result = 404
    return result


""" DECORATORS """
@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


""" ROUTING """
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
    return render_template('blog_entries.html', entries=entries[:10])


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
    elif request.method == 'POST':
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
        except:
            photo = None

        for key in data:
            if data[key] == "":
                data[key] = None

        data['published'] = datetime.now()

        if request.form.get('twitter'):
            data['syndication'] = tweeter.main(data, photo=photo) + ","
        if request.form.get('instagram'):
            pass #todo: add posse to instagram
        if request.form.get('tumblr'):
            pass #todo: add posse to tumblr
        location = createEntry(data, image=data['photo'], g=g)
        return redirect(location)
    else:
        return redirect('/404'), 404


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

        if request.form.get('twitter'):
            data['syndication'] = tweeter.main(data, photo=photo) + ","
        if request.form.get('instagram'):
            pass #todo: add posse to instagram
        if request.form.get('tumblr'):
            pass #todo: add posse to tumblr
        file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
        entry = get_bare_file(file_name+".md")
        location = editEntry(data, old_entry=entry, g=g)
        return redirect(location)


@app.route('/data/<year>/<month>/<day>/image/<name>')
def image_fetcher_depricated(year, month, day, name):
    """ do not use---old image fetcher """
    entry = 'data/{year}/{month}/{day}/image/{name}'.format(year=year, month=month, day=day, type=type, name=name)
    print(entry)
    img = open(entry)
    print(img)
    return send_file(img)


@app.route('/data/<year>/<month>/<day>/<name>')
def image_fetcher(year, month, day, name):
    """ Retruns a specific image """
    entry = 'data/{year}/{month}/{day}/{name}'.format(year=year, month=month, day=day, type=type, name=name)
    img = open(entry)
    return send_file(img)


def get_mentions(url):
    r = requests.get(url)
    mentions = []
    try:
        p = r.json()
        for link in p['links']:
            mentions.append(link['data'])
    except:
        pass
    return mentions


@app.route('/e/<year>/<month>/<day>/<name>')
def profile(year, month, day, name):
    """ Get a specific article """
    # try:
    file_name = "data/{year}/{month}/{day}/{name}".format(year=year, month=month, day=day, name=name)
    entry = file_parser(file_name+".md")
    if os.path.exists(file_name+".jpg"):
        entry['photo'] = file_name+".jpg" # get the actual file
    if os.path.exists(file_name+".mp4"):
        entry['video'] = file_name+".mp4" # get the actual file
    if os.path.exists(file_name+".mp3"):
        entry['audio'] = file_name+".mp3" # get the actual file
    mentions = get_mentions('http://kongaloosh.com/e/{year}/{month}/{day}/{name}'.
                            format(year=year, month=month, day=day, name=name))
    app.logger.info(mentions)
    return render_template('entry.html', entry=entry, mentions=mentions)
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
def handleMicroPub():
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

                # data = dict((k, v) for k, v in data.iteritems() if v)
                if not data['published']:
                    data['published'] = datetime.today()
                else:
                    data['published'] = parse(data['published'])

                try:
                    img = request.files.get('photo')
                    data['photo'] = img
                except: pass

                try:
                    audio = request.files.get('audio').read()
                    data['audio'] = audio
                except: pass

                try:
                    video = request.files.get('video').read()
                    data['video'] = video
                except: pass

                syndication = ''
                try:
                    if('twitter.com' in data['syndicate-to[]']):
                        try:
                            syndication += tweeter.main(str(data['content']).encode('utf-8'), data['photo'])
                        except:
                            syndication += tweeter.main(str(data['content']).encode('utf-8'))
                    if('tumblr.com' in data['syndicate-to[]']):
                        try:
                            pass
                        except:
                            pass
                    if('instagram' in data['syndicate-to[]']):
                        try:
                            pass
                        except:
                            pass
                except:
                    pass
                data['syndication'] = syndication

                location = createEntry(data, image=data['photo'], g=g)

                resp = Response(status="created", headers={'Location':'http://kongaloosh.com/'+location})
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
                # 'facebook.com/',
                'twitter.com/',
                'instagram.com/',
                # 'linkedin.com/'
            ]
            r = ''
            while len(syndicate_to) > 1:
                r += 'syndicate-to[]=' + syndicate_to.pop() + '&'
            r += 'syndicate-to[]=' + syndicate_to.pop()
            resp = Response(content_type='application/x-www-form-urlencoded', response=r)
            return resp
        return 'not implemented', 501


@app.route('/webmention', methods=['POST'])
def handleWebmention():
    app.logger.info('handleWebmention [%s]' % request.method)
    if request.method == 'POST':
        valid = False
        source = request.form.get('source')
        target = request.form.get('target')
        vouch = request.form.get('vouch')
        app.logger.info('source: %s target: %s vouch %s' % (source, target, vouch))

        valid = validURL(target)

        app.logger.info('valid? %s' % valid)

        f = open('mention.txt', 'w+')
        f.write(str(source) + str(target))

        if valid == requests.codes.ok:
            if mention(source, target, vouch):
                return redirect(target)
            else:
                if vouch is None and cfg['require_vouch']:
                    return 'Vouch required for webmention', 449
                else:
                    return 'Webmention is invalid', 400
        else:
            return redirect('/404'), 404


if __name__ == "__main__":
    app.run(debug=True)
