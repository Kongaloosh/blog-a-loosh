import requests
from bs4 import BeautifulSoup
import html2text
import markdown2
__author__ = 'alex'


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

if __name__ == '__main__':
    entry = get_entry_content('https://kylewm.com/2015/08/you-could-take-another-look-at-your-mf2-e-content')
    # entry = get_entry_content('http://rhiaro.co.uk/2015/08/ilooklikeanengineer')
    # entry = get_entry_content('https://aaronparecki.com/notes/2015/08/03/5/')
    # entry = get_entry_content('https://waterpigs.co.uk/notes/4cMEwe/')
    print entry['content']
    # get_entry_content('http://127.0.0.1:5000/e/2015/8/1/things')
