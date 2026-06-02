import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/voice/test-tts',
    data=json.dumps({'text': 'hello', 'provider': 'piper', 'piper_voice': 'en_US-ryan-medium'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    urllib.request.urlopen(req)
    print("200 OK")
except urllib.error.HTTPError as e:
    print(f"ERROR {e.code}:")
    print(e.read().decode())
