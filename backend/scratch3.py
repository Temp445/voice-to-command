import google.generativeai as genai
import asyncio

async def main():
    genai.configure(api_key="fake-api-key-1234")
    model = genai.GenerativeModel("gemini-1.5-flash")
    chat = model.start_chat()
    try:
        resp = await chat.send_message_async("Reply with exactly: OK")
        print("SUCCESS:", resp.text)
    except Exception as e:
        print("FAILED:", str(e))

if __name__ == "__main__":
    asyncio.run(main())
