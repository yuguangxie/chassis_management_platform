import urllib.request
print(urllib.request.urlopen("http://127.0.0.1:8800/api/v1/health", timeout=3).read().decode())
