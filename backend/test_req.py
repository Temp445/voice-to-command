import urllib.request, json, urllib.error
data = json.dumps({'text': 'hello', 'provider': 'piper', 'piper_voice': 'en_US-ryan-medium'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/voice/test-tts', data=data, headers={'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print(e.read().decode())
