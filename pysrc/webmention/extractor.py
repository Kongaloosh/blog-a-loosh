import requests
from bs4 import BeautifulSoup

__author__ = 'alex'

def get_entry_content(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    entry ={}
    try:
        entry_full = soup.find_all(class_="hentry")[0]
    except:
        entry_full = soup.find_all(class_="h-entry")[0]
    try:
        entry['author'] = soup.find(class_="p-author").find(class_='p-name').text
    except:
        entry['author'] = soup.find(class_="p-author").find(class_='p-name')

    if entry['author'] == '':
        entry['author'] = soup.find(class_="p-author").find(class_='p-name')['value']

    if entry['author'] == None:
        entry['author'] = soup.find(class_="p-author")['title']

    entry['published'] = soup.find_all(class_='dt-published')[0].contents[0]
    entry['content'] =   soup.find(class_='e-content')
    entry['url'] = url

    return entry

if __name__ == '__main__':
    get_entry_content('http://rhiaro.co.uk/2015/08/ilooklikeanengineer')
    get_entry_content('https://aaronparecki.com/notes/2015/08/03/5/')
    get_entry_content('https://waterpigs.co.uk/notes/4cMEwe/')
    get_entry_content('http://tantek.com/2015/214/b1/alaska-cruise-log-day-1')