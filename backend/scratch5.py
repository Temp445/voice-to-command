import google.generativeai as genai
import asyncio
import os

async def main():
    # 1. Start with VALID key
    valid_key = os.environ.get("GEMINI_API_KEY", "")
    genai.configure(api_key=valid_key)
    
    # Send a message to open the connection
    model1 = genai.GenerativeModel("gemini-1.5-flash")
    c1 = model1.start_chat()
    print("M1:", (await c1.send_message_async("Reply OK")).text.strip())
    
    # 2. Change to INVALID key
    print("Reconfiguring...")
    genai.configure(api_key="invalid-key-12345")
    
    # Send a message again
    model2 = genai.GenerativeModel("gemini-1.5-flash")
    c2 = model2.start_chat()
    try:
        print("M2:", (await c2.send_message_async("Reply OK")).text.strip())
        print("BUG FOUND: Gemini is caching the old connection!")
    except Exception as e:
        print("EXPECTED FAILURE:", str(e))

if __name__ == "__main__":
    asyncio.run(main())
