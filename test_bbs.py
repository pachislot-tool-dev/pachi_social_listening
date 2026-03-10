import requests
from bs4 import BeautifulSoup

url = "https://www2.5ch.io/5ch.html"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers)
resp.encoding = 'shift_jis'

soup = BeautifulSoup(resp.text, 'html.parser')
links = soup.find_all('a')
for link in links:
    if 'スロット' in link.text or 'slotk' in (link.get('href') or ''):
        print(link.text, link.get('href'))
