"""
    This module deals with retrieving webmention details
"""

__author__ = 'alex'

import requests

def get_mentions(url):
    """We fetch all the webentions of a particular entry"""
    r = requests.get(url)
    mentions = []
    try:
        p = r.json()
        for link in p['links']:
            mentions.append(link['data'])
    except:
        pass
    return mentions
