import requests
import re


s = requests.Session()
s.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
}
s.timeout = 3
while True:
    site = input()
    if 'https' in site:
        s.proxies = {
            'https': site
        }
    else:
        s.proxies = {
            'http': site
        }
    try:
        pp = s.get('https://javlog.com/')
        if pp.status_code == 200:
            print('可用')
        else:
            print('不可用')
    except:
        print('出错！')
