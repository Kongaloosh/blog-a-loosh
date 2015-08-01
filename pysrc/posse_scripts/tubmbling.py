__author__ = 'alex'
import pytumblr
import oauth2
import urlparse

REQUEST_TOKEN_URL = 'http://www.tumblr.com/oauth/request_token'
AUTHORIZATION_URL = 'http://www.tumblr.com/oauth/authorize'
ACCESS_TOKEN_URL = 'http://www.tumblr.com/oauth/access_token'
CONSUMER_KEY = 'irsyCC1SeBW25a7eJJHz2zjSf1wwaVw5zEFRmp8lZUDyCBanQ2'
CONSUMER_SECRET = 'GoycBjtaHwnEqtH0Rt38MuBHXkK9PV0nhEVMSNVAYAmfbDXddq'

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