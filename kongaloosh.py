import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, make_response
from contextlib import closing
import os
import redis
import ninka
import urllib2
import requests
import ronkyuu
import ninka
import datetime
from mf2py.parser import Parser
from datetime import datetime
import pickle
from urlparse import urlparse, ParseResult

# configuration
DATABASE = '/tmp/kongaloosh.db'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'Anubis'
PASSWORD = 'Munc4kin))'

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
cfg = None

##################DATABASE#########################

def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def connect_db():
    return sqlite3.connect(app.config['DATABASE'])

##################WEB MENTION######################


def processWebmention(sourceURL, targetURL, vouchDomain=None):
    result = False
    r      = requests.get(sourceURL, verify=False)
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
        for domain in h.readlines():
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


def checkAccessToken(access_token):
    """Check if the given access token matches any in the data stored

    code=gk7n4opsyuUxhvF4&
    redirect_uri=https://example.com/auth&
    client_id=https://example.com/
    """

    '''
        access_token = 'a'
        headers = {'code':access_token, 'redirect_uri':'kongaloosh.com/auth', 'client_id':'https://example.com/'}
        request = requests.post(url="https://indieauth.com/auth/", headers=headers)
        handler = urllib2.HTTPHandler()
        opener = urllib2.build_opener(handler)
        request = urllib2.Request(url="https://indieauth.com/auth/")

        request.add_header("Content-Type",'application/json')
        request.get_method = lambda: "GET"

        try:
            connection = opener.open(request)
        except urllib2.HTTPError,e:
            connection = e

        access_token = ""
        connection = httplib.HTTPSConnection("https://indieauth.com",80)
        headers = {'code':access_token, 'redirect_uri':'kongaloosh.com/auth/', 'client_id':'https://example.com/'}
        connection.request("POST","/auth/",headers)
        response = connection.getresponse()
    '''
    f1=open('testfile', 'w+')
    f1.write('ninaaa')
    f1.close()
    r = ninka.indieauth.validateAuthCode(code=access_token, client_id='https://kongaloosh.com/', redirect_uri='https://kongaloosh.com/')
    return r['status'] == requests.codes.ok



def processMicropub(data):
    '''
        'h', 'name', 'summary', 'content', 'published', 'updated', 'category',
        'slug', 'location', 'in-reply-to', 'repost-of', 'syndication', 'syndicate-to'
    '''
    dict((k, v) for k, v in data.iteritems() if v)
    if createEntry(data):

        return make_response("", 200)
    else:
        return ('Unable to process Micropub %s' % request.method, 400, [])


def createEntry(data, image=None):
    time=datetime.now()
    file_path = "data/{year}/{month}/{day}/{type}/".format(year=time.year, month=time.month, day=time.day, type=data['h'])
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path))
    pickle.dump(data, open(file_path+"/{title}.txt".format(title=data['name']),'wb'))
    if image:
        file = open(file_path+"/{title}-img.jpg".format(title=data['name']),'w')
        file.write(image)
        file.close()
    return True


def processWebmention(sourceURL, targetURL, vouchDomain=None):
    result = False
    r      = requests.get(sourceURL, verify=False)
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
        g.db.execute('insert into mentions (content_text, source_url, target_url, post_date) values (?, ?, ?, ?)',
                 [mentionData['content'], mentionData['sourceURL'], mentionData['targetURL'], mentionData['postDate']])
        g.db.commit()

    return result


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

noteTemplate = """<span id="%(url)s"><p class="byline h-entry" role="note"> <a href="%(url)s">%(name)s</a> <time datetime="%(date)s">%(date)s</time></p></span>
%(marker)s
"""


##################REQUEST ARGS#####################

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

################## ROUTING ########################

@app.route('/')
def show_entries():
    entries = []
    for subdir, dir, files  in os.walk("data", topdown=True):
        for file in files:
            if file.endswith('.p'):
                p = pickle.load(open(subdir+os.sep+file))
                entries.append(p)

        if len(entries) == 10: break

    return render_template('show_entries.html', entries=entries)

@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        abort(401)
    g.db.execute('insert into entries (title, text, date_published) values (?, ?, ?)',
                 [request.form['title'], request.form['text'], datetime.datetime.now()])
    g.db.commit()
    flash('New entry was successfully posted')
    return redirect(url_for('show_entries'))

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
            flash('You were logged in')
            return redirect(url_for('show_entries'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))


@app.route('/micropub', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def handleMicroPub():
    f1=open('testfile', 'w+')
    f1.write('endpoint recieving')
    f1.close()   
    app.logger.info('handleMicroPub [%s]' % request.method)
    if request.method == 'POST':
        access_token = request.headers.get('Authorization')
        if access_token:
            access_token = access_token.replace('Bearer ', '')
            f1=open('testfile', 'w+')
            f1.write('tokeeeeeen time {token}'.format(token=access_token))
            f1.close()
            if checkAccessToken(access_token) or True:
                data = {}
                for key in ('h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                    'slug', 'location', 'in-reply-to', 'repost-of', 'syndication', 'syndicate-to'):
                    data[key] = request.form.get(key)
                
#		f1.write('it is alive!')
#		f1.close()
		return processMicropub(data)
            else:
#		f1.write('this is a 403')
#		f1.close()
                return 'unauthorized', 403
        else:
#	    f1.write('this is a 401')
#	    f1.close()
            return 'unauthorized', 401
    elif request.method == 'GET':
        # add support for /micropub?q=syndicate-to
        return 'not implemented', 501


@app.route('/webmention', methods=['POST'])
def handleWebmention():
    app.logger.info('handleWebmention [%s]' % request.method)
    if request.method == 'POST':
        valid  = False
        source = request.form.get('source')
        target = request.form.get('target')
        vouch  = request.form.get('vouch')
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
            return 'invalid post', 404


if __name__ == "__main__":
    app.run(debug=True)
