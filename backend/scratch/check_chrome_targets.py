import urllib.request
import json

try:
    with urllib.request.urlopen("http://127.0.0.1:9222/json") as r:
        targets = json.loads(r.read().decode())
        print("Success! Targets:")
        for t in targets:
            print(f"- Type: {t.get('type')}, URL: {t.get('url')}, Title: {t.get('title')}")
except Exception as e:
    print("Error connecting to Chrome on 127.0.0.1:9222:", e)
