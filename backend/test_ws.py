import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://127.0.0.1:8000/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected. Listening for messages...")
            # Trigger the API call in the background
            import urllib.request
            import threading
            def trigger():
                try:
                    urllib.request.urlopen("http://127.0.0.1:8000/api/test/suggestion")
                    print("API triggered.")
                except Exception as e:
                    print("API trigger failed:", e)
            threading.Timer(1.0, trigger).start()

            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print("Received:", data)
                if data.get("type") == "transcript":
                    print("SUCCESS! Transcript received:", data["payload"])
                    break
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test_ws())
