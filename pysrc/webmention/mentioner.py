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
    url = re.sub('["\ ]','',url)
    return url


def send_mention(source, target):
    """Sends a webmention to a target site from our source link"""
    try:
        endpoint = find_end_point(target)
        payload = {'source': source, 'target': target}
        headers = {'Accept': 'text/html, application/json'}
        r = requests.post('https://webmention.io/kongaloosh.com/webmention', data=payload, headers=headers)
    except:
        pass


if __name__ == '__main__':
    send_mention(
        'http://kongaloosh.com/e/2015/8/2/this-is-a-test-note-to-use-as-a-source-for-sending-web-mentions',
        'http://kongaloosh.com/e/2015/8/1/im-so-glad-andrew-donnelly-is-mcing-the-canmore-folk-fest-too-this-year-its-going-to-be-a-blast')