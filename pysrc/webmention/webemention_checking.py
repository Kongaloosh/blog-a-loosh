"""
    This module deals with retrieving webmention details
"""

__author__ = 'alex'

import requests

def get_mentions(url):
    """We fetch all the webe"""
    mentions = []
    try:
        r = requests.get('http://webmention.io/api/mentions?target='+url)
        p = r.json()
        for link in p['links']:
            if link['data']['content']:
		mentions.append(link['data'])
    except:
        pass
    return mentions

if __name__ == '__main__':
    m = get_mentions('http://kongaloosh.com/e/2015/8/3/another-test-note-for-webmentions')
    print(len(m))
