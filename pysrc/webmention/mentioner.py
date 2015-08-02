"""
 Collection of methods which relate to sending webmentions.

"""

__author__ = 'alex'

import requests
import re


def find_end_point(target):
    """Uses regular expressions to find a site's webmention endpoint"""
    html = requests.get(target)
    search_result = re.search('(rel(\ )*=(\ )*(")*webmention)(")*(.)*',html.content).group()
    url = re.search('((?<=href=)(\ )*(")*(.)*(")*)(?=/>)', search_result).group()
    url = re.sub('["]','',url)
    return url


def send_mention(source, target):
    """Sends a webmention to a target site from our source link"""
    try:
        endpoint = target(find_end_point())
        headers = {'source': source, 'target': target}
        requests.request(endpoint, headers=headers)
    except:
        pass


if __name__ == '__main__':
    find_end_point('http://aaronparecki.com/')
    # send_mention('http://kongaloosh.com/e/2015/8/2/this-is-a-test-note-to-use-as-a-source-for-sending-web-mentions','https://kartikprabhu.com/notes/test-note-totally-te')