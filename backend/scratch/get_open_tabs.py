import urllib.request
import json

try:
    with urllib.request.urlopen("http://localhost:9222/json", timeout=1) as r:
        targets = json.loads(r.read())
        print(f"Total targets: {len(targets)}")
        for t in targets:
            print(f"- Type: {t.get('type')}, Title: {t.get('title')}, URL: {t.get('url')}, ID: {t.get('id')}")
except Exception as e:
    print(f"Error fetching: {e}")
