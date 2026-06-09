import sys
import os
import asyncio
import websockets
import json
import wave
import io

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
workspace_dir = os.path.abspath(os.path.join(backend_dir, '..'))
sys.path.insert(0, backend_dir)
sys.path.insert(0, workspace_dir)

from voice.tts.piper_synthesizer import PiperSynthesizer
from app.config import settings

async def simulate_frontend_mic():
    print("Initializing TTS...")
    tts = PiperSynthesizer()
    tts.voice = settings.piper_voice
    
    text = "Open the CRM dashboard."
    print(f"Synthesizing test command: '{text}'")
    wav_bytes = await tts.synthesize(text)
    
    with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
        raw_pcm = w.readframes(w.getnframes())
        
    print("Connecting to backend websocket (ws://127.0.0.1:8000/ws)...")
    async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
        print("Connected. Sending trigger_listen command (Simulating 'Skip Wake Word' button click)...")
        await ws.send(json.dumps({"type": "trigger_listen"}))
        
        # Wait 500ms for pipeline to transition to LISTENING
        await asyncio.sleep(0.5)
        
        print("Streaming synthesized audio chunks (simulating frontend microphone)...")
        # Stream audio chunks (960 bytes = 30ms)
        for i in range(0, len(raw_pcm), 960):
            chunk = raw_pcm[i:i+960]
            await ws.send(chunk)
            await asyncio.sleep(0.03) # Real-time simulation
            
        print("Finished speaking. Waiting for pipeline to detect silence and process...")
        
        # Listen for state changes
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                if isinstance(msg, str):
                    data = json.loads(msg)
                    if data.get("event") == "pipeline_state":
                        state = data["data"]["state"]
                        print(f"[UI UPDATE] Pipeline State changed to: {state.upper()}")
                        if state == "idle":
                            print("Pipeline returned to idle. Test complete.")
                            break
                    elif data.get("event") == "transcript":
                        txt = data["data"]["text"]
                        print(f"[UI UPDATE] Transcript updated: '{txt}'")
                    elif data.get("event") == "command_executed":
                        cmd = data["data"]["raw_text"]
                        print(f"[UI UPDATE] Command Executed: '{cmd}'")
            except asyncio.TimeoutError:
                print("Timed out waiting for response.")
                break

if __name__ == "__main__":
    asyncio.run(simulate_frontend_mic())
