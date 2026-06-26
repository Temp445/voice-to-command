import urllib.request
import json

try:
    with urllib.request.urlopen("http://127.0.0.1:9222/json") as r:
        targets = json.loads(r.read().decode())
        print(json.dumps(targets, indent=2))
except Exception as e:
    print("Error:", e)
