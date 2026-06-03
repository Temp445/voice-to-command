import asyncio
from loguru import logger
import json

from automation.browser.browser_testing import BrowserTestRunner

async def main():
    runner = BrowserTestRunner()
    
    tests = [
        {
            "name": "Google Search Test",
            "steps": [
                {"action": "search_google", "params": {"query": "playwright python"}},
                {"action": "assert_text_exists", "params": {"text": "playwright"}},
                {"action": "scroll", "params": {"direction": "down", "amount": 1000}}
            ]
        },
        {
            "name": "Tab Management & Wikipedia",
            "steps": [
                {"action": "new_tab", "params": {"url": "https://en.wikipedia.org/wiki/Web_testing"}},
                {"action": "assert_text_exists", "params": {"text": "software testing"}},
                {"action": "scroll", "params": {"direction": "down", "amount": 500}},
                {"action": "switch_tab", "params": {"index": 0}} # Switch back to Google
            ]
        },
        {
            "name": "YouTube Search & Play",
            "steps": [
                {"action": "new_tab", "params": {"url": "https://www.youtube.com"}},
                {"action": "search_youtube", "params": {"query": "lofi hip hop radio"}},
                {"action": "wait_for_selector", "params": {"selector": "ytd-video-renderer a#video-title"}},
                {"action": "click", "params": {"selector": "ytd-video-renderer a#video-title"}},
                {"action": "play_pause", "params": {}}
            ]
        }
    ]
    
    logger.info("Starting test runner...")
    results = []
    for test in tests:
        res = await runner.run_test(test)
        results.append(res)
        print(json.dumps(res, indent=2))
        
    # Write to a JSON file to parse easily
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Close it after test
    await runner.engine.close_browser()

if __name__ == "__main__":
    asyncio.run(main())
