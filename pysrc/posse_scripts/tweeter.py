# -*- coding: utf-8 -*-
__author__ = 'alex'
import tweepy
from slugify import slugify
import re
import ConfigParser


def get_keys():
    config = ConfigParser.ConfigParser()
    config.read('config.ini')
    cfg = {}
    cfg['access_token'] = config.get('Twitter', 'AccessToken')
    cfg['access_token_secret'] = config.get('Twitter', 'AccessTokenSecret')
    cfg['consumer_key'] = config.get('Twitter', 'ConsumerKey')
    cfg['consumer_secret'] = config.get('Twitter', 'ConsumerSecret')
    
    return cfg


def get_api(cfg):
    """Authenticates for API access"""
    auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
    auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
    return tweepy.API(auth)


def main(data):
    """Posts a thread of tweets based on the text of a post.
    Args:
        data (dict): A dict which represents a post.
    Returns:
        url (str): The url of the first tweet in the thread.
        """
    # Fill in the values noted in previous step here
    cfg = get_keys()        # grab keys
    api = get_api(cfg)      # setup API
    tweets = text_to_tweets(data=data['content'], url=data['url'])  # process string into tweet thread
    status = api.update_status(status=tweets.pop(0))                # post the first tweet so that we have a status id
    first_id = status.id                                            # the id which points to origin of thread
    for tweet in tweets:
        status = api.update_status(status=tweet, in_reply_to_status_id=status.id)
    return ('http://twitter.com/{name}/status/{id}'.format(name=status.user.screen_name, id=first_id))


def text_to_tweets(data, url):
    """unrolls text into a list of strings which correspond to a full tweet.
    Args:
        data (str): the text to be unrolled into a twitter thread.
        url (str): the url which the tweet should point towards.
    """
    max_chars = 240-1-23                # one removed for punctuation 22 removed for link.
    data = data.split('\n').join('')    # strip newlines.
    text = re.findall(r"[\w']+|[.!?;]", data)
    tweets = []
    tweet = ""
    while len(text) > 0:
        try:
            while len(tweet) + len(text[0]) + 1 < max_chars:
                phrase = text.pop(0)
                if phrase not in ['?', "."]:
                    tweet += " "
                tweet += phrase

            if text[0] in ['?', "."]:     # if the next char is a punctuation mark
                # print text
                tweet += text.pop(0)      # add it to the end of the tweet
            else:
                tweet += u'…'             # otherwise '...'

            if len(tweets) == 0:            # if there are presently no tweets, we need to add the blog link to the post
                max_chars = 240-1           # we can now use more characters.
                tweet += " " + url        #
        except IndexError:
            pass
        tweets.append(tweet)
        tweet = ""
        # print text
    return tweets


def social_link(data):
    return data['url']


if __name__ == "__main__":
    tweets = process_tweet("""
    I'm going back through my dive logbook after a three year diving hiatus. The software I use to track my dives has become an ungodly mess of company acquisitions and software maintenance. Turns out the company that made my dive-computer was bought out by scuba-pro. To even get my hands on the software to open my dive-log file, I had to scour looking for a hidden link that would take me to the SmartTrak site. That wasn't even enough alone, I had to engage in browser witchcraft to coerce the site to not redirect me to scuba-pro's main site. The file is _nowhere else_, at least by my searching. Interesting that no one liked it enough to keep a mirror of it... Of course, the software didn't solve my problems. _oh no_. The dates were incorrect on some of my dives. Another example malady of poor software support: I could turn the background of dive profiles _gradient olive green_, but I could not edit basic dive info---e.g., the date and location of a dive. For the first-time in my life, I'm actually facing a deprecation of software that I _need_. It's important that I keep the data I collect when I'm diving. After going through old dev-forums and [dive-forums](https://www.scubaboard.com/community/threads/smart-trak-to-logtrak-import.546613/page-2), I found [a converter](https://thetheoreticaldiver.org/rch-cgi-bin/smtk2ssrf.pl) which takes shameful SmartTrack files and converts them into a modified XML for use with [SubSurface](https://subsurface-divelog.org/download/). At least I can coerce the file into being read as XML, rather than proprietary nonsense. More than that, not only does sub-surface allow me to edit the date of a dive in increments greater than 7, I can edit _multiple_ dives at the same time. It's the future. I can't help but feel that this is a sort of digital vagrancy. SubSurface seems great now, but what about in 3 years? 10 years? I know there's a trend of web-based [dive-logs](https://en.divelogs.de/), but I don't want to have to shuffle around, converting what has no business being anything but XML or a CSV to bunch of proprietary, uninterpretable file formats. Having been burnt by SmartTrack, I'm looking for robust export functionality. Luck for me, it seems sub-surface is able to export as CSVs. This seems like a clear candidate to make a stand and own my own data. It's just screaming to be added to the blog. Then if something breaks, it's my own damn fault.
""", "https://example.com")
    for i in tweets:
        print len(i)