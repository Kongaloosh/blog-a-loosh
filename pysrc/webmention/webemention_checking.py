import requests
"""
    This module deals with retrieving webmention details
"""

__author__ = 'alex'


def get_mentions(url):
    """We fetch all the webe"""
    mentions = []
    reposts = 0
    likes = 0
    try:
        r = requests.get('https://webmention.io/api/mentions?target='+url)
        print 'https://webmention.io/api/mentions?target='+url
        p = r.json()
        for link in p['links']:
            if link['activity']['type'] == 'like':
                likes += 1
            elif link['activity']['type'] == 'repost':
                reposts += 1
            else:
                mentions.append(link['data'])
    except:
        pass
    return (mentions, likes, reposts)

if __name__ == '__main__':
    (m,l,r) = get_mentions('https://kongaloosh.com/e/2018/8/12/one-of-my-favorite-parts-of-edmfolkfest-is-the-ckuaradio-tent-with-their-live-broadcasts')
    print l,r
