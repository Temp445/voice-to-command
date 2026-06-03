"""
Browser Test Runner.
Executes JSON-defined test cases against the Browser Engine.
"""

from loguru import logger
from automation.browser.browser_engine import BrowserEngine

class BrowserTestRunner:
    def __init__(self):
        self.engine = BrowserEngine()

    async def run_test(self, test_case: dict) -> dict:
        """
        Executes a test case and returns a detailed report.
        test_case format:
        {
            "name": "Test Name",
            "steps": [
                {"action": "navigate", "params": {"url": "example.com"}},
                {"action": "assert_text_exists", "params": {"text": "Domain"}}
            ]
        }
        """
        logger.info(f"Running test: {test_case['name']}")
        report = {
            "name": test_case["name"],
            "status": "passed",
            "steps": [],
            "error": None
        }

        try:
            for i, step in enumerate(test_case.get("steps", [])):
                action = step.get("action")
                params = step.get("params", {})
                step_result = {"step": i + 1, "action": action, "status": "passed"}

                try:
                    if action == "navigate":
                        await self.engine.navigate(params["url"])
                    elif action == "search_google":
                        await self.engine.search_google(params["query"])
                    elif action == "search_youtube":
                        await self.engine.search_youtube(params["query"])
                    elif action == "wait_for_selector":
                        page = await self.engine.ensure_browser()
                        await page.wait_for_selector(params["selector"], timeout=10000)
                    elif action == "assert_text_exists":
                        content = await self.engine.extract_page_content()
                        if params["text"].lower() not in content.lower():
                            raise AssertionError(f"Text '{params['text']}' not found in page.")
                    elif action == "click":
                        await self.engine.click(params["selector"])
                    elif action == "new_tab":
                        await self.engine.new_tab(params.get("url"))
                    elif action == "switch_tab":
                        if "index" in params:
                            await self.engine.switch_tab(params["index"])
                        elif "url" in params:
                            await self.engine.switch_tab_by_url(params["url"])
                    elif action == "scroll":
                        await self.engine.scroll(params.get("direction", "down"), params.get("amount", 500))
                    elif action == "play_pause":
                        await self.engine.play_pause()
                    else:
                        raise ValueError(f"Unknown test action: {action}")
                        
                    step_result["message"] = "Success"
                except Exception as e:
                    step_result["status"] = "failed"
                    step_result["error"] = str(e)
                    report["status"] = "failed"
                    report["error"] = f"Failed at step {i + 1} ({action}): {e}"
                    
                    # Take screenshot on failure
                    try:
                        screenshot_path = await self.engine.screenshot(f"fail_{test_case['name'].replace(' ', '_')}.png")
                        step_result["screenshot"] = screenshot_path
                    except Exception:
                        pass
                        
                    report["steps"].append(step_result)
                    break # Stop test on first failure
                    
                report["steps"].append(step_result)

        except Exception as e:
            report["status"] = "error"
            report["error"] = str(e)

        logger.info(f"Test {test_case['name']} completed with status: {report['status']}")
        return report
