"""Container-local health probe without credentials or project data."""
import http.client
import os
from urllib.parse import urlsplit

connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=5)
connection.request('GET', '/healthz', headers={'Host': urlsplit(os.environ['WAN_STUDIO_ORIGIN']).netloc})
response = connection.getresponse()
raise SystemExit(0 if response.status == 200 else 1)
