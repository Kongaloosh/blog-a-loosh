import requests
from bs4 import BeautifulSoup

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
        entry['content'] = soup.find(class_='e-content').text
    except AttributeError:
        pass
    entry['url'] = url
    return entry
    return entry

if __name__ == '__main__':
    # get_entry_content('http://rhiaro.co.uk/2015/08/ilooklikeanengineer')
    # get_entry_content('https://aaronparecki.com/notes/2015/08/03/5/')
    # get_entry_content('https://waterpigs.co.uk/notes/4cMEwe/')
    get_entry_content('http://127.0.0.1:5000/e/2015/8/1/things')