import requests
from requests.exceptions import MissingSchema
import re
from bs4 import BeautifulSoup
import html2text
import markdown2

"""
 Collection of methods which relate to sending webmentions.
 see https://www.w3.org/TR/webmention/ for details.
"""

__author__ = 'kongaloosh'


def find_end_point(source_website):
    """Uses regular expressions to find a site's webmention endpoint
    
    Args:
        source_website: a string which represents the website which we want to parse and the.
    Returns:
        A webmention link parsed from the source website as a string.
    Raises:
        If the request returns a MissingSchema error, we catch it and re-raise it with a description. 
    """

    try:
        #  get the source website
        r = requests.get(source_website)
    except MissingSchema:
        raise MissingSchema("Source website was malformed; could not complete request: {0}".format(source_website))

    # find tags with the rel="webmention", indicating that it links to a webmention endpoint
    search_result = re.search('rel\ *=\ *\"*webmention\"*.*href\ *=\"\ *(.*)\"', r.content)
    if search_result:
        # if there is a result to the regular expression...
        # pick up the captured regular expression group which corresponds to the href url.
        search_result = search_result.group(1)
        if type(search_result) == list:
            # if there were multiple webmention tags, pick the first for the url
            return search_result[0]
        else:
            # return the webmention url
            return search_result
    else:
        # if we couldn't find any rel="webmention" tags, there's not endpoint; return None
        return None


def send_mention(source, target, endpoint=None):
    """Sends a webmention to a target site from our source link
    
    Args:
        source: the specific page which mentions the target; we are sending a mention to the endpoint for mentioning 
        the target page.
        target: the specific page the source mentions; the page we send a mention for to the enpoint for.
        endpoint: optional argument which defines the url the mention is sent to. If none is specified, the webmention 
        tag is parsed from the target's html using find_end_point
        
    Returns:
        request r.
    """

    if not endpoint:
        # if no endpoint was specified, parse it from the page we are mentioning
        endpoint = find_end_point(target)

    payload = {'source': source, 'target': target}
    headers = {'Accept': 'text/html, application/json'}
    r = requests.post(endpoint, data=payload, headers=headers)
    return r


def get_mentions(url):
    """Fetches the webmentions for a given url from https://webmention.io. 
    
    If you don't have an account already, you must sign up and perform the necessary steps to recieve webmentions.
    Args:
        url: the url of the page which webmentions are being fetched for.
        
    Returns:
        (mentions, likes, reposts)
        mentions: the mentions stored as a list of dictionaries.
        likes: the number of likes for the url
        reposts: the number of reposts for the url
    
    
    """
    mentions = []
    reposts = 0
    likes = 0

    r = requests.get('https://webmention.io/api/mentions?target='+url)
    p = r.json()

    for link in p['links']:
        if link['activity']['type'] == 'like':
            likes += 1
        elif link['activity']['type'] == 'repost':
            reposts += 1
        else:
            mentions.append(link['data'])
    return mentions, likes, reposts


def get_entry_content(url):
    print "requesting " + str(url)
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    entry = {}
    try:
        entry_full = soup.find_all(class_="hentry")[0]
    except (IndexError, AttributeError):
        try:
            entry_full = soup.find_all(class_="h-entry")[0]
        except (IndexError, AttributeError):
            pass

    try:
        entry['author'] = soup.find(class_="p-author").find(class_='p-name').text
    except (KeyError, AttributeError):
        try:
            entry['author'] = soup.find(class_="p-author").find(class_='p-name')
        except AttributeError:
            pass

    try:
        if entry['author'] == '':
            entry['author'] = soup.find(class_="p-author").find(class_='p-name')['value']
    except (KeyError, AttributeError):
        pass

    try:
        if entry['author'] == None:
            entry['author'] = soup.find(class_="p-author")['title']
    except KeyError:
        pass

    try:
        entry['published'] = soup.find_all(class_='dt-published')[0].contents[0]
    except IndexError:
        pass
    try:
        h = html2text.HTML2Text()
        h.ignore_links = False
        post = ' '.join([str(i) for i in soup.find(class_='e-content').contents])
        entry['content'] = markdown2.markdown(h.handle(post))
    except AttributeError:
        pass
    entry['url'] = url
    return entry


