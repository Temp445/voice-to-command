import google.generativeai as genai
import asyncio

async def main():
    model = genai.GenerativeModel("gemini-1.5-flash", client_options={"api_key": "fake-key-9999"})
    chat = model.start_chat()
    try:
        resp = await chat.send_message_async("Reply OK")
        print("SUCCESS:", resp.text.strip())
    except Exception as e:
        print("FAILED AS EXPECTED:", str(e))

if __name__ == "__main__":
    asyncio.run(main())
