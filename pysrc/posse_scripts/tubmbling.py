__author__ = 'alex'
import pytumblr
import oauth2
import urlparse
import ConfigParser

config = ConfigParser.ConfigParser()
config.read('config.ini')


REQUEST_TOKEN_URL = config.get('Tumblr', 'REQUEST_TOKEN_URL')
AUTHORIZATION_URL = config.get('Tumblr', 'AUTHORIZATION_URL')
ACCESS_TOKEN_URL = config.get('Tumblr', 'ACCESS_TOKEN_URL')
CONSUMER_KEY = config.get('Tumblr', 'CONSUMER_KEY')
CONSUMER_SECRET = config.get('Tumblr', 'CONSUMER_SECRET')

def main(text, data):
    consumer = oauth2.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
    client = oauth2.Client(consumer)

    resp, content = client.request(REQUEST_TOKEN_URL, "GET")

    request_token = dict(urlparse.parse_qsl(content))
    OAUTH_TOKEN = request_token['oauth_token']
    OAUTH_TOKEN_SECRET = request_token['oauth_token_secret']

    print "Request Token:"
    print " - oauth_token = %s" % OAUTH_TOKEN
    print " - oauth_token_secret = %s" % OAUTH_TOKEN_SECRET

    client = pytumblr.TumblrRestClient(
    CONSUMER_KEY,
    CONSUMER_SECRET,
    OAUTH_TOKEN,
    OAUTH_TOKEN_SECRET
    )

    tags = data['categories'].split(',')
    format = "markdown"

    try:
        client.create_photo('yourBlogName', state="published", tags=["testing", "ok"], data="image.jpg")
        return
    except:
        pass

    try:
        client.create_audio()
        return
    except:
        pass

    try:
        client.create_video()
        return
    except:
        pass

    client.create_text()
    return
