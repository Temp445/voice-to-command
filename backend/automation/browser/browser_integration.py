"""
Browser Integration Blueprint
---------------------------------
This file demonstrates how to wire the BrowserController into a FastAPI application.
It includes the lifespan event for startup/shutdown, WebSocket routing for real-time
browser commands, and an example of hooking it into a faster-whisper pipeline.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, APIRouter
from loguru import logger
from automation.browser.browser_controller import BrowserController, BrowserLauncher, VoiceBrowserCommands

# --- 1. Lifespan Integration ---

@asynccontextmanager
async def browser_lifespan(app: FastAPI):
    """
    FastAPI lifespan manager that launches Chrome with CDP enabled
    and connects the controller on startup.
    """
    logger.info("Starting Browser Integration...")
    
    # Force launch/restart Chrome with CDP port
    success = BrowserLauncher.launch(port=9222)
    if not success:
        logger.error("Failed to launch Chrome with CDP. Browser automation disabled.")
    else:
        # Connect the singleton controller
        ctrl = BrowserController()
        await ctrl.connect()
        logger.info("Browser Controller connected.")
        
    yield
    
    # Cleanup on shutdown
    ctrl = BrowserController()
    await ctrl.disconnect()
    logger.info("Browser Controller disconnected.")

# Initialize app with lifespan
app = FastAPI(lifespan=browser_lifespan)
browser_router = APIRouter(prefix="/browser", tags=["Browser Automation"])

# --- 2. REST Endpoints ---

@browser_router.post("/command")
async def execute_voice_command(transcript: str):
    """
    Example endpoint to send a raw voice transcript to the browser NLP mapper.
    """
    commands = VoiceBrowserCommands()
    response = await commands.execute(transcript)
    return {"status": "success", "response": response}

@browser_router.get("/tabs")
async def list_tabs():
    """Returns a list of currently open tabs."""
    ctrl = BrowserController()
    tabs = await ctrl.get_all_tabs()
    return {"tabs": [{"url": t.url, "title": await t.title()} for t in tabs]}

# --- 3. WebSocket Integration ---

@browser_router.websocket("/ws")
async def browser_websocket(websocket: WebSocket):
    """
    Real-time WebSocket endpoint for the React frontend to control the browser.
    """
    await websocket.accept()
    commands = VoiceBrowserCommands()
    
    try:
        while True:
            data = await websocket.receive_json()
            transcript = data.get("command", "")
            if transcript:
                response = await commands.execute(transcript)
                await websocket.send_json({"status": "success", "response": response})
    except Exception as e:
        logger.error(f"WebSocket disconnected: {e}")

# Register router
app.include_router(browser_router)

# --- 4. Whisper Pipeline Hook Example ---
"""
How to hook this into your existing faster-whisper pipeline:

async def handle_voice_command(transcript: str):
    # 1. Check if the intent is a browser command
    browser_keywords = ["open", "search", "click", "scroll", "play", "tab"]
    
    if any(kw in transcript.lower() for kw in browser_keywords):
        # 2. Route to ACEBrowserCommands
        commands = VoiceBrowserCommands()
        response = await commands.execute(transcript)
        
        # 3. Speak the response via TTS (piper/gtts)
        await tts_service.speak(response)
        return True
        
    # fallback to other intents...
"""
