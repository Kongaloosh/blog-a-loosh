# -*- coding: utf-8 -*-
import tweepy
import requests
import re
import ConfigParser

config = ConfigParser.ConfigParser()
config.read('config.ini')

# configuration
DEBUG = config.get('Global', 'Debug')
SECRET_KEY = config.get('Global', 'DevKey')
USERNAME = config.get('SiteAuthentication', "Username")
PASSWORD = config.get('SiteAuthentication', 'password')
DOMAIN_NAME = config.get("Global", "DomainName")
# the url to use for showing recent bulk uploads

ALBUM_GROUP_RE = re.compile(
    r'''@{3,}([\s\S]*?)@{3,}'''
)
IMAGES_GROUP_RE = re.compile(
    r'''(?<=\){1})[ ,\n,\r]*-*[ ,\n,\r]*(?=\[{1})'''
)
IMAGE_REF_RE = re.compile(
    r'''\({1}([\s\S]*)\){1}'''
)


def get_keys():
    """
    Gets the keys from the configuration file of the blog.
    """
    config = ConfigParser.ConfigParser()
    config.read('config.ini')
    cfg = {}
    cfg['access_token'] = config.get('Twitter', 'AccessToken')
    cfg['access_token_secret'] = config.get('Twitter', 'AccessTokenSecret')
    cfg['consumer_key'] = config.get('Twitter', 'ConsumerKey')
    cfg['consumer_secret'] = config.get('Twitter', 'ConsumerSecret')
    
    return cfg


def get_api(cfg):
    """
    Authenticates for API access of twitter using Tweepy using a given

    Args:
        cfg (ConfigParser): an instance of ConfigParser for the blogsource. Must have the consumer_secret and
        access_token_secret in order for the api to be instantiated.
    Returns:
        api (tweepy.API): an instance of the tweepy api.
    """
    auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
    auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
    return tweepy.API(auth)


def send_tweet(data):
    """Posts a thread of tweets based on the text of a post.
    Args:
        data (dict): A dict which represents a post.
    Returns:
        url (str): The url of the first tweet in the thread.
        """
    # Fill in the values noted in previous step here
    cfg = get_keys()        # grab keys
    api = get_api(cfg)      # setup API
    in_reply_to = None
    twitter_url = 'https://twitter.com'
    if data['in_reply_to'] is not None:                     # if post is reply ...
        for reply in data['in_reply_to']:
            if reply[:len(twitter_url)] == twitter_url:     # if the URL points to twitter ...
                in_reply_to = reply.split('/')[-1:]         # ... get the status id
    url = 'https://' + DOMAIN_NAME + data['url']
    tweets = post_to_tweets(data=data['content'], url=url)  # process string into tweet thread
    # post the first tweet so that we have a status id to start the thread
    status = api.update_status(status=tweets.pop(0), in_reply_to_status_id=in_reply_to)
    first_id = status.id    # the id which points to origin of thread
    try:
        lat,lng = data['geo'][4:].split(",")
    except KeyError:
        lat, lng = None, None
    for tweet in tweets:
        status = api.update_status(status=tweet, in_reply_to_status_id=status.id)
    return 'http://twitter.com/{name}/status/{id}'.format(name=status.user.screen_name, id=first_id, lat=lat, lng=lng)


def text_to_tweets(text, url):
    """
    A function which takes the

    Args:
        text (str): The full text of the post to be converted into tweets.
        url (str): The url of the post; where the post is located at the blog domain.
    Returns:
        tweets (list): a list of strings which expresses a thread of tweets.
    """
    max_chars = 240 - 1 - 23    # one removed for punctuation 22 removed for link.
    tweets = []                 # buffer of tweets to send
    tweet = ""                  # the current tweet we are composing
    while len(text) > 0:        # while we still have text ...
        try:
            while len(tweet) + len(text[0]) + 1 < max_chars:
                # as long as the composed tweet is one less than the character limit
                phrase = text.pop(0)
                if phrase not in ["? ", ". ", "! "]:    # If the next piece of text is not punctuation ...
                    tweet += " "                        # ... Add a space
                    tweet += phrase                     # and add the text
                else:
                    tweet += phrase[0]

            # if the net character is a punctuation mark
            if text[0] in ["? ", ". "]:  # if the next char is a punctuation mark

                tweet += text.pop(0)[0]  # add it to the end of the tweet
            else:
                tweet += u'…'  # otherwise '...'
        except IndexError:
            print("INDEX ERROR")           # ... something went wrong ...

        if len(tweets) == 0 and url is not None:
            # If there are presently no tweets we need to add the blog link to the post
            # This tells someone where to see your posts.
            max_chars = 240 - 1     # we can now use more characters.
            tweet += " " + url      #

        tweets.append(tweet)
        tweet = ""

    return tweets


def find_all_images(text):
    albums = ALBUM_GROUP_RE.findall(text)       # for all albums in the text ...
    parsed_albums = []                          # where we store the image refs
    for album in albums:
        parsed_albums.append([])                # make a new list for all the images
        images = IMAGES_GROUP_RE.split(album)   # for all images in an album ...
        for image in images:
            parsed_albums[-1].append(IMAGE_REF_RE.findall(image)[0])    # append the image ref.
    return parsed_albums


def load_all_images(refs):
    for album in refs:
        for idx, image in enumerate(album):
            r = requests.get(image)
            if r.status_code == 200:
                album[idx] = r.content
            else:
                album.pop(idx)
    return album


def strip_text(data):
    data = ''.join(data.split('\n'))    # strip newlines.
    data = re.split('@{3,}[\s\S]*?@{3,}',data)

    for idx, element in enumerate(data):
        stripped = re.sub(r'\(https?:\/\/[^\s]+\)', '', element)                         # remove URLS
        data[idx] = re.sub(r'(\[)([\w\s\d.?\-\",\'!@#$%^&*]*)(\])', r'\2', stripped)     # no links, just names
        if len(data[idx]) == 0:
            data.pop(idx)

    return data


def post_to_tweets(data, url):
    """unrolls text into a list of strings which correspond to a full tweet.
    Args:
        data (str): the text to be unrolled into a twitter thread.
        url (str): the url which the tweet should point towards.
    """

    print("here,", url)

    albums = find_all_images(data['content'])
    text = strip_text(data['content'])

    """Where applicable, the images are associated with the text. This means, that to make an appropriate thread the
    conversion from a post to tweets should take into account how words relate to images in a spacial way. For this
    reason, we convert to tweets in batches."""

    cfg = get_keys()  # grab keys
    api = get_api(cfg)  # setup API
    in_reply_to = None
    twitter_url = 'https://twitter.com'

    # for idx, caption in enumerate(text):
    #     if idx > 0:
    #         url_img = None
    #     caption = re.findall(r"[\w']+|[.!?;]\ ", caption)
    #     text[idx] = text_to_tweets(caption, url_img)

    try:
        if data['in_reply_to'] is not None:  # if post is reply ...
            for reply in data['in_reply_to']:
                if reply[:len(twitter_url)] == twitter_url:     # if the URL points to twitter ...
                    in_reply_to = reply.split('/')[-1:]         # ... get the status id
    except KeyError:
        pass

    url = 'https://' + DOMAIN_NAME + url

    tweets = text_to_tweets(text, url=url)             # process string into tweet thread

    # try and parse a lat lng.
    try:
        lat, lng = data['geo'][4:].split(",")
    except KeyError:
        lat, lng = None, None

    # post the first tweet so that we have a status id to start the thread
    status = api.update_status(status=tweets[0].pop(0), in_reply_to_status_id=in_reply_to)
    first_id = status.id  # the id which points to origin of thread

    for album_group in text:
        try:
            media = album_group.pop(0)      # get the corresponding album
            for tweet in album_group:
                status = api.update_with_media(filename=media, status=tweet, in_reply_to_status_id=status.id, lat=lat, long=lng)
                media = None
        except IndexError:  # if we're out of albums...
            pass
    return 'http://twitter.com/{name}/status/{id}'.format(name=status.user.screen_name, id=first_id, lat=lat, lng=lng)


def social_link(data):
    return data['url']


if __name__ == "__main__":
    post = {"content":"I'm going back through my dive logbook after a three year diving hiatus. @@@@[img_loc]()@@@ The software I use to track my dives has become an ungodly mess of company acquisitions and software maintenance. Turns out the company that made my dive-computer was bought out by scuba-pro. To even get my hands on the software to open my dive-log file, I had to scour looking for a hidden link that would take me to the SmartTrak site. That wasn't even enough alone, I had to engage in browser witchcraft to coerce the site to not redirect me to scuba-pro's main site. The file is _nowhere else_, at least by my searching. @@@@[img_loc]()@@@ Interesting that no one liked it enough to keep a mirror of it... Of course, the software didn't solve my problems. _oh no_. The dates were incorrect on some of my dives. Another example malady of poor software support: I could turn the background of dive profiles _gradient olive green_, but I could not edit basic dive info---e.g., the date and location of a dive. For the first-time in my life, I'm actually facing a deprecation of software that I _need_. It's important that I keep the data I collect when I'm diving. After going through old dev-forums and [dive-forums](https://www.scubaboard.com/community/threads/smart-trak-to-logtrak-import.546613/page-2), I found [a converter](https://thetheoreticaldiver.org/rch-cgi-bin/smtk2ssrf.pl) which takes shameful SmartTrack files and converts them into a modified XML for use with [SubSurface](https://subsurface-divelog.org/download/). At least I can coerce the file into being read as XML, rather than proprietary nonsense. More than that, not only does sub-surface allow me to edit the date of a dive in increments greater than 7, I can edit _multiple_ dives at the same time. It's the future. I can't help but feel that this is a sort of digital vagrancy. SubSurface seems great now, but what about in 3 years? 10 years? I know there's a trend of web-based [dive-logs](https://en.divelogs.de/), but I don't want to have to shuffle around, converting what has no business being anything but XML or a CSV to bunch of proprietary, uninterpretable file formats. Having been burnt by SmartTrack, I'm looking for robust export functionality. Luck for me, it seems sub-surface is able to export as CSVs. This seems like a clear candidate to make a stand and own my own data. It's just screaming to be added to the blog. Then if something breaks, it's my own damn fault."}
    tweets = post_to_tweets(data=post, url="https://example.com")
    for i in tweets:
        print(i)
        print('\n')

