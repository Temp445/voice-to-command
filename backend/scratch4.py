import google.generativeai as genai
import asyncio
import os

async def main():
    # 1. Configure with a VALID key from environment
    valid_key = os.environ.get("GEMINI_API_KEY", "")
    print(f"Testing with valid key: {valid_key[:5]}...")
    genai.configure(api_key=valid_key)
    
    # 2. Make a request to ensure channel is open
    model = genai.GenerativeModel("gemini-1.5-flash")
    chat = model.start_chat()
    try:
        resp = await chat.send_message_async("Reply OK")
        print("FIRST SUCCESS:", resp.text.strip())
    except Exception as e:
        print("FIRST FAILED:", str(e))
        return

    # 3. Configure with INVALID key
    print("Reconfiguring with INVALID key...")
    genai.configure(api_key="fake-api-key-1234")
    
    # 4. Make request again
    model2 = genai.GenerativeModel("gemini-1.5-flash")
    chat2 = model2.start_chat()
    try:
        resp2 = await chat2.send_message_async("Reply OK")
        print("SECOND SUCCESS:", resp2.text.strip())
    except Exception as e:
        print("SECOND FAILED:", str(e))

if __name__ == "__main__":
    asyncio.run(main())
