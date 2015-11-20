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


def send_mention(source, target, endpoint=None):
    """Sends a webmention to a target site from our source link"""
    try:
        if not endpoint:
            endpoint = find_end_point(target)
        payload = {'source': source, 'target': target}
        headers = {'Accept': 'text/html, application/json'}
        r = requests.post(endpoint, data=payload, headers=headers)
        return r
    except:
        pass


if __name__ == '__main__':
    s = 'http://kongaloosh.com/e/2015/11/20/heres-a-test-to-see-if-i-can-get-bridgy-to-post-to-facebook-for-me'
    t = "http://brid.gy/publish/facebook"
    r = send_mention(s,t,endpoint='https://brid.gy/publish/webmention')
    print(r)
    print(r.text)
    print(r.json())
    # from webemention_checking import get_mentions
    # print len(get_mentions(t))