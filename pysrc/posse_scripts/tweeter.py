# -*- coding: utf-8 -*-
__author__ = 'alex'
import tweepy
from slugify import slugify

def get_keys():
    cfg = {}
    cfg['access_token'] = open('config/twitter/twitter_access_token','rb').read()
    cfg['access_token_secret'] = open('config/twitter/twitter_access_token_secret','rb').read()
    cfg['consumer_key'] = open('config/twitter/twitter_consumer_key','rb').read()
    cfg['consumer_secret'] = open('config/twitter/twitter_consumer_secret','rb').read()
    return cfg

def get_api(cfg):
    auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
    auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
    return tweepy.API(auth)

def main(data, photo=None):
    # Fill in the values noted in previous step here
    cfg = get_keys()

    api = get_api(cfg)
    short_length = api.configuration()['short_url_length']
    tweet = process_tweet(data=data, short_length=short_length)

    if photo and len(tweet)<117:
        status = api.update_with_media(filename="tweet.jpg", file=photo, status=tweet)
    else:
        status = api.update_status(status=tweet)
    return ('http://twitter.com/{name}/status/{id}'.format(name=status.user.screen_name, id=status.id))


def process_tweet(data, short_length):
    status = data['social_content']
    link = social_link(data)
    max_len = 140-short_length-1
    if len(status) > max_len:
        status = status[:max_len-1]+ u'…'
    return status +" "+ link

def social_link(data):
    if not data['name'] == None:    #is it an article
        slug = data['name']
    else:
        slug = (data['content'].split('.')[0])
    slug = slugify(slug)

    return 'kongaloosh.com/e/{year}/{month}/{day}/{slug}'.format(
            year = str(data['published'].year),
            month = str(data['published'].month),
            day = str(data['published'].day),
            slug = str(slug))

if __name__ == "__main__":
    main()
