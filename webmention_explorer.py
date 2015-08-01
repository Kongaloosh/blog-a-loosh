__author__ = 'alex'
import requests

r = requests.get('http://webmention.io/api/mentions?target=http://kongaloosh.com/e/2015/7/31/i-hooked-my-brain-up-to-a-computer-today-for-science')
p = r.json()
for link in p['links']:
    print(link.keys())
    print(link['data'])