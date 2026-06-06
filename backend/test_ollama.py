import asyncio
import sys

from loguru import logger
from app.services.llm.adapters.ollama_adapter import OllamaAdapter

async def main():
    logger.info("Initializing Ollama Adapter...")
    # Change the model name if you have a different one downloaded, e.g., "llama3.1"
    adapter = OllamaAdapter(api_key="http://localhost:11434", model="llama3.2")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! Can you write a short haiku about coding?"}
    ]
    
    logger.info("Testing standard chat...")
    try:
        response = await adapter.chat(messages, max_tokens=100)
        logger.info(f"Response: {response}")
    except Exception as e:
        logger.error(f"Chat failed. Make sure Ollama is running locally and the model is pulled. Error: {e}")
        return

    logger.info("Testing stream chat...")
    try:
        async for chunk in adapter.stream_chat(messages, max_tokens=100):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        logger.error(f"Stream failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
