# -*- coding: utf-8 -*-
__author__ = 'alex'
import tweepy
from slugify import slugify

def get_api(cfg):
    auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
    auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
    return tweepy.API(auth)

def main(data, photo=None):
    # Fill in the values noted in previous step here
    cfg = {
        "consumer_key": "DVjfycLdIZzr0gzC442VfEmjd",
        "consumer_secret": "PFvWgbQvvLVJb5lhJxDlWAIgXd7X5Yt7fh08nd69Hi2eRaI04q",
        "access_token": "785209428-XTDjPkQ3a48Z32rXoT6st9SAqcAj1IoVEvQJxEvM",
        "access_token_secret": "NX7iD7CEmLimGwWQjqzZ9xHwGLSasWVp8yt3dvg0DmCIg"
    }

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
        slug = (data['content'].split('.')[0])[:10]
    slug = slugify(slug)

    return 'kongaloosh.com/e/{year}/{month}/{day}/{slug}'.format(
            year = str(data['published'].year),
            month = str(data['published'].month),
            day = str(data['published'].day),
            slug = str(slug))

if __name__ == "__main__":
    main()
