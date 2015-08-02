"""
    This module deals with retrieving webmention details
"""

__author__ = 'alex'

import requests

def get_mentions(url):
    """We fetch all the webe"""
    mentions = []
    try:
        header = {'target': url}
        r = requests.get('http://webmention.io/api/mentions', header=header)
        p = r.json()
        for link in p['links']:
            mentions.append(link['data'])
    except:
        pass
    return mentions
