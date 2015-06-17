import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, make_response, Response
from contextlib import closing
import os
from operator import itemgetter
import requests
import ronkyuu
import ninka
from mf2py.parser import Parser
from datetime import datetime
import pickle
from slugify import slugify
import re
# configuration
DATABASE = '/tmp/kongaloosh.db'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'Anubis'
PASSWORD = 'Munc4kin))'

templates = {

'note':
"""
p-name:
    title:{title}
    slug:{slug}
e-content:{content}
dt-published:{date_time}
p-category:{category}
u-syndication:
    {syndication}
"""

        ,

'article':
"""
p-name:
    title:{title}
    slug:{slug}
p-summary:{summary}
e-content:{content}
dt-published:{date_time}
p-category:{category}
u-syndication:
    {syndication}
"""

    ,

'reply':
"""
p-name:
    title:{title}
    slug:{slug}
e-content:{content}
dt-published:{date_time}
dt-updated:{updated}
p-category:{category}
u-syndication:
    {syndication}
u-in-reply-to:
    {reply-to}
"""

    ,

'like':
"""
p-name:
    title:{title}
    slug:{title_slug}
u-like-of
    {likes}
"""
        ,

'photo':
"""
p-name:
    title:{title}
    slug:{slug}
e-content:{content}
dt-published:{date_time}
p-category:{category}
p-location:
    {location}
u-syndication:
    {syndication}
u-photo
    {photo}
"""
        ,

'bookmark':
"""
p-name:
    title:{title}
    slug:{slug}
e-content:{content}
dt-published:{date_time}
p-category:{category}
u-bookmark-of:{book_mark}
"""
    ,

'checkin':
"""
p-name:
    title:{title}
    slug:{slug}
e-content:{content}
dt-published:{date_time}
p-category:{category}
p-location:
    {location}
u-syndication:
    {syndication}
"""
    ,
'repost':
"""
p-name:
    title:{title}
    slug:{slug}
p-summary:{summary}
e-content:{content}
dt-published:{date_time}
dt-updated:{updated}
p-author:{author}
p-category:{category}
u-repost-of
    {repost}
"""
        ,

'rsvp':
"""
p-name:
    title:{title}
    slug:{slug}
e-content:{content}
dt-published:{date_time}
p-category:{category}
p-location:
    time-zone:{timezone}
    lat:{lat}
    long:{long}
    location-name:{loc_name}
u-syndication:
    {syndication}
u-in-reply-to:
    {reply-to}
"""
    ,

'event':
"""
p-name:
    title:{title}
    slug:{slug}
p-summary:{summary}
e-content:{content}
dt-published:{date_time}
p-location:
    time-zone:{timezone}
    lat:{lat}
    long:{long}
    location-name:{loc_name}
u-syndication:
    {syndication}
"""
    ,

'video':
"""
p-name:
    title:{title}
    slug:{slug}
e-content:{content}
dt-published:{date_time}
p-category:{category}
u-url:{url}
u-uid:{id}
u-syndication:
    {syndication}
u-video
    {video}
"""
    ,

'audio':
"""
p-name:
    title:{title}
    slug:{slug}
p-summary:{summary}
e-content:{content}
dt-published:{date_time}
dt-updated:{updated}
p-author:{author}
p-category:{category}
u-url:{url}
u-uid:{id}
p-location:
    time-zone:{timezone}
    lat:{lat}
    long:{long}
    location-name:{loc_name}
u-syndication:
    {syndication}
u-audio
    {audio}
u-video
    {video}
u-like
    {like}
p-repost
    {repost}
p-featured
    {featured}
"""

}



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

    f1=open('testfile', 'w+')
    f1.write('ninaaa')
    f1.close()
    r = ninka.indieauth.validateAuthCode(code=access_token, client_id='https://kongaloosh.com/', redirect_uri='https://kongaloosh.com/')
    return r['status'] == requests.codes.ok

def createVideo(data, video):
    pass


def createImage(image, category, content, location, published=datetime.now(), syndication=None):

    if content == None:
        raise "no content in submission"

    title = content.split('.')[0]
    slug = slugify(title)

    if category == None:
        # todo: Keyword extraction.
        pass
    entry = templates['photo'].format(
        title=title, slug=slug, content=content,
        date_time=published , category=category, syndication=syndication,
        location=location, photo=image
    )
    return (entry,slug)

def createAudio(data, audio):
    pass


def createNote(category, content, published=datetime.now(), syndication=None):

    if content == None:
        raise "no content in submission"

    title = content.split('.')[0]
    slug = slugify(title)

    if category == None:
        # todo: Keyword extraction.
        pass
    entry = templates['note'].format(
        title=title, slug=slug, content=content,
        date_time=published, category=category, syndication=syndication
    )
    return (entry,slug)

def createArticle(title, content, category, published=datetime.now(), syndication=None):

    if content == None or content == None:
        raise "Incomplete submission"

    slug = slugify(title)

    if category == None:
        # todo: Keyword extraction.
        pass
    entry = templates['article'].format(
        title=title, slug=slug, content=content,
        date_time=published,category=category, syndication=syndication
    )
    return (entry,slug)

def createCheckin(category, content, location, published=datetime.now(), syndication=None):
    if content == None or location == None:
        raise "no content in submission"

    title = content.split('.')[0]
    slug = slugify(title)

    if category == None:
        # todo: Keyword extraction.
        pass
    entry = templates['checkin'].format(
        title=title, slug=slug, content=content,
        date_time=datetime, category=category, syndication=syndication,
        location=location
    )
    return (entry,slug)


def createReply(data):
    pass


def createRepost(data):
    pass


def createEntry(data, image=None, video=None, audio=None):
    '''
         'h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                    'slug', 'location', 'in-reply-to', 'repost-of', 'syndication', 'syndicate-to'
    '''
    # event: 2deep4me

    # rsvp: reply with p-rsvp status

    # like: no name or title, but like-of
    title = ''

    try: syndication = data['syndication']
    except: syndication = None

    try: location = data['location']
    except: None

    try: category = data['category']
    except: None

    if not data['name'] == None: #is it an article
        type = 'article'
        # multiple paragraphs, title
        (entry, title) = createArticle(
            title=data['name'], content=data['content'],category=data['category']
            ,published=data['published'],syndication=syndication)


    elif video: # is it a video
        # video: no name or title, but video
        type = 'video'


    elif audio: # is it audio
        type = 'audio'


    elif image: # is it an image
        type = 'image'
        # image: no name or title, but image
        (entry,title) = createImage(
            image=image, category=category, content=data['content'],
            location=location, published=data['published'], syndication=syndication)


    elif not data['in-reply-to'] == None: # is it a response
        data['in-reply-to']
        type = 'comment'
        # reply: no name or title, but in-reply-to


    elif not data['in-reply-to'] == None: # is it a repost
        data['repost of']
        type = 'repost'
        # u-repost-of


    elif not data['location'] == None:# is it a checkin
        data['location']
        type = 'checkin'
        # check-in: note with location

    else:
        type = 'note'
        (entry,title) = createNote(
            category=category, content=data['content'],
            published=data['published'], syndication=syndication )

    #otherwise it's a plain note


    time=datetime.now()
    file_path = "data/{year}/{month}/{day}/{type}/".format(year=time.year, month=time.month, day=time.day, type=type)
    # pickle.dump(open(title, 'gawd', 'wb'))
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path))
    total_path =  file_path+"{title}".format(title=title)
    if not os.path.isfile(total_path+'.md'):
        file = open(total_path+".md", 'wb')
        file.write(entry)
        file.close()
        if image:
            file = open(total_path+title+".jpg",'w')
            file.write(image)
            file.close()
        return total_path

    else:
        i = 1
        while(True):
            if not os.path.isfile(total_path+"-{num}.md".format(num=i)):
                file= open(total_path+'-{num}.md'.format(num=i), 'wb')
                file.write(entry)
                file.close()
                if image:
                    file = open(total_path+"-{num}.jpg".format(num=i),'wb')
                    file.write(image)
                    file.close()
                return total_path+"-{num}".format(num=i)
            else: i += 1


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


def file_parser(f):
    f = open(f, 'r')
    str = f.readall()
    e = {}
    try: e['title'] = re.search('(?<=title:)(.)*', str).group()
    except: pass
    try: e['slug'] = re.search('(?<=slug:)(.)*', str).group()
    except: pass
    try: e['p-summary'] = re.search('(?<=p-summary:)(.)*', str).group()
    except: pass
    try: e['e-content'] = re.search('(?<=e-content:)(.)*', str).group()
    except: pass
    try: e['dt-published'] = re.search('(?<=dt-published:)(.)*', str).group()
    except: pass
    try: e['p-author'] = re.search('(?<=p-author:)(.)*', str).group()
    except: pass
    try: e['p-category'] = re.search('(?<=p-category:)(.)*', str).group()
    except: pass
    try: e['u-url'] = re.search('(?<=u-url:)(.)*', str).group()
    except: pass
    try: e['u-uid'] = re.search('(?<=u-uid:)(.)*', str).group()
    except: pass
    try: e['time-zone'] = re.search('(?<=time-zone:)(.)*', str).group()
    except: pass
    try: e['lat'] = re.search('(?<=lat:)(.)*', str).group()
    except: pass
    try: e['long'] = re.search('(?<=long:)(.)*', str).group()
    except: pass
    try: e['syndication'] = re.search('(?<=syndication:)(.)*', str).group()
    except: pass
    try: e['location-name'] = re.search('(?<=location-name:)(.)*', str).group()
    except: pass

    return e

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

##################DECORATORS#####################

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
        dir.sort(reverse=True)
        for file in files:
            if file.endswith('.md'):
                e = file_parser(f=subdir+os.sep+file)
                try:
                    e['photo'] = subdir + '/' + file.split('.')[0]+".jpg" # get the actual file
                except:pass
                entries.append(e)
        if len(entries) >= 10: break
        entries = sorted(entries, key=itemgetter('published'), reverse=True)

    return render_template('show_entries.html', entries=entries)


@app.route('/<year>/<month>/<day>/<type>/<name>')
def profile(year, month, day, type, name):
    # try:
    entry = "data/{year}/{month}/{day}/{type}/{name}".format(year=year, month=month, day=day, type=type, name=name)
    pickle.load(open(entry+".p", "wb"))
    return render_template('show_entries.html', entries=entry)
    # except:
    #     return 404


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
    app.logger.info('handleMicroPub [%s]' % request.method)
    if request.method == 'POST':
        access_token = request.headers.get('Authorization')
        if access_token:
            access_token = access_token.replace('Bearer ', '')
            if checkAccessToken(access_token) or True:
                data = {}
                for key in (
                        'h', 'name', 'summary', 'content', 'published', 'updated', 'category',
                    'slug', 'location', 'in-reply-to', 'repost-of', 'syndication', 'syndicate-to'):
                    data[key] = request.form.get(key)

                # data = dict((k, v) for k, v in data.iteritems() if v)
                data['published'] = datetime.today()
                # try:
                img = request.files.get('photo').read()
                data['img'] = img
                location = createEntry(data, img)
                # except: location = createEntry(data)

                resp = Response(status="created", headers={'Location':'http://kongaloosh.com'+location})
                resp.status_code = 201
                return resp
            else:
                return 'unauthorized', 403
        else:
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
