"""
    This module deals with retrieving webmention details
"""

__author__ = 'alex'

import requests

def get_mentions(url):
    """We fetch all the webe"""
    mentions = []
    try:
        print(url)
        r = requests.get('http://webmention.io/api/mentions?target='+url)
        p = r.json()
        for link in p['links']:
            mentions.append(link['data'])
        print(r)
        print(p)
    except:
        pass
    return mentions

if __name__ == '__main__':
    get_mentions('http://kongaloosh.com/e/2015/8/1/im-so-glad-andrew-donnelly-is-mcing-the-canmore-folk-fest-too-this-year-its-going-to-be-a-blast')