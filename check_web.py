import urllib.request
url = 'https://www.pdbbind.org.cn/'
with urllib.request.urlopen(url, timeout=20) as r:
    data = r.read(500).decode('utf-8', 'ignore')
print(data)
