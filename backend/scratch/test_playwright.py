import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Test 1: Evaluating a function string
        js_func = """
        async (args) => {
            console.log("HELLO FROM EVALUATE FUNCTION STRING", args);
            return args.x + args.y;
        }
        """
        try:
            res = await page.evaluate(js_func, {"x": 5, "y": 10})
            print("Test 1 Result:", res)
        except Exception as e:
            print("Test 1 Error:", e)

        # Test 2: Evaluating an IIFE string
        js_iife = """
        (async (args) => {
            console.log("HELLO FROM IIFE", args);
            return args.x + args.y;
        })({"x": 5, "y": 10})
        """
        try:
            res = await page.evaluate(js_iife)
            print("Test 2 Result:", res)
        except Exception as e:
            print("Test 2 Error:", e)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
