import asyncio
import time
import os
import sys

# Ensure backend root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.command_service import command_service

test_cases = [
    "Open Notepad",
    "Take a screenshot",
    "Volume up by 20",
    "Mute the audio",
    "Lock my screen",
    "Open my Downloads folder",
    "Close the current window",
    "Open Chrome",
    "Search Google for python tutorials",
    "Open YouTube and play jazz music",
    "Open my CRM",
    "Go to the CRM dashboard",
    "Scroll down",
    "Refresh the page",
    "What time is it?",
    "Stop listening"
]

async def run_tests():
    print(f"{'Command':<40} | {'Intent':<25} | {'Latency (ms)':<15}")
    print("-" * 85)
    
    total_latency = 0
    
    for text in test_cases:
        start = time.perf_counter()
        
        # We only want to test routing/intent parsing speed to prove NLU is instant
        # We don't want to actually execute them (like locking the screen)
        # So we just call _regex_match and _fuzzy_match directly
        intent_name, params = command_service._regex_match(text)
        if not intent_name:
            intent_name, params = command_service._fuzzy_match(text)
            
        latency = (time.perf_counter() - start) * 1000
        total_latency += latency
        print(f"{text:<40} | {str(intent_name):<25} | {latency:.2f} ms")

    print("-" * 85)
    print(f"Average Intent Routing Latency: {total_latency/len(test_cases):.2f} ms")

if __name__ == "__main__":
    asyncio.run(run_tests())
