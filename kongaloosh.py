# all the imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash
from contextlib import closing

# configuration
DATABASE = '/tmp/kongaloosh.db'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'Anubis'
PASSWORD = 'Munc4kin))'

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)

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
    cur = g.db.execute('select title, text from entries order by id desc')
    entries = [dict(title=row[0], text=row[1]) for row in cur.fetchall()]
    return render_template('show_entries.html', entries=entries)

@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        abort(401)
    g.db.execute('insert into entries (title, text) values (?, ?)',
                 [request.form['title'], request.form['text']])
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