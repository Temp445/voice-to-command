import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.intent_registry import get_registry

tests = [
    "open Notepad",
    "open Calculator",
    "what time is it?",
    "are you there?",
    "Open Visual Studio Code",
    "Open Chrome and search FastAPI tutorial",
    "Open WhatsApp",
    "Create a new folder called Projects",
    "What is the weather today?",
    "Open Chrome",
    "Search for FastAPI",
    "Open VS Code",
    "Create a Python file",
    "Name it test.py",
    "Open Notepad",
    "Write 'Hello World'",
    "Save it on the desktop",
    "Close it",
    "Open Calculator",
    "Close Calculator",
    "Minimize Chrome",
    "Maximize VS Code",
    "Switch to Chrome",
    "Close all Notepad windows",
    "Open Task Manager",
    "Open File Explorer",
    "Open YouTube",
    "Search for Python tutorial",
    "Play the first video",
    "Open Gmail",
    "Open GitHub",
    "Search for OpenAI",
    "Open the first result",
    "Scroll down",
    "Go back",
    "Refresh the page",
    "Create a folder named ACE",
    "Create a text file named notes.txt",
    "Rename notes.txt to tasks.txt",
    "Move tasks.txt to Desktop",
    "Delete tasks.txt",
    "Open Downloads folder",
    "Show recent files",
    "Open VS Code",
    "Create a new Python file",
    "Write a Hello World program",
    "Save the file as app.py",
    "Run the Python file",
    "Close VS Code",
    "Increase volume to 80%",
    "Decrease volume to 20%",
    "Mute volume",
    "Unmute volume",
    "Lock my computer",
    "Open Settings",
    "Open Control Panel",
    "Show system information",
    "Read the text on my screen",
    "What is written in this document?",
    "Extract text from this image",
    "Summarize the content on screen",
    "Read the error message on screen",
    "Open Discord",
    "Open Spotify",
    "Open Steam",
    "Open Adobe Reader",
    "What applications are installed?",
    "What applications are currently running?",
    "Open Chrome and search for FastAPI",
    "Open VS Code and create a Python file",
    "Open Notepad and write meeting notes",
    "Open YouTube and play relaxing music",
    "Create a folder and save a text file inside it",
    "Open File Explorer and navigate to Downloads",
    "I need a code editor",
    "I want to watch a movie",
    "I need software for video editing",
    "Prepare my machine for Python development",
    "Suggest tools for AI development",
    "How can I improve my coding productivity?",
    "Open Chrome",
    "Search for OpenAI",
    "Open the first result",
    "Summarize this page",
    "Save the summary in a text file",
    "Read it aloud",
    "Close Notepad",
    "Close Microsoft Word",
    "Restart my computer",
    "Shut down my computer",
    "Close all applications",
    "Find all PDF files on my computer",
    "Open the latest downloaded file",
    "Show files modified today",
    "Find screenshots taken this week",
    "Open the most recently used application",
    "Clean temporary files",
    "Check available disk space",
    "Open Chrome, search FastAPI tutorials, summarize the first result, save the notes, and read them aloud."
]

async def main():
    registry = get_registry()
    print("Command | Intent | Handled by")
    print("-" * 50)
    for cmd in tests:
        intent, kwargs = registry.match_intent(cmd)
        if intent:
            print(f"{cmd[:30]:30} | {intent.name:20} | Built-in")
        else:
            print(f"{cmd[:30]:30} | {'LLM Fallback':20} | LLM")

if __name__ == '__main__':
    asyncio.run(main())
