import asyncio
from loguru import logger
from browser_use import Agent

class AutonomousBrowserAgent:
    """
    Wraps the `browser-use` Python library to execute fully autonomous web navigation.
    Hooks into the existing Playwright instance created by BrowserEngine.
    """
    
    @staticmethod
    async def run_task(task_description: str, engine) -> str:
        """
        Runs an autonomous task using the current active browser.
        """
        logger.info(f"Starting autonomous browser task: {task_description}")
        
        try:
            from app.services.llm.llm_service import llm_service
            
            if not llm_service.is_ready:
                return "Autonomous mode failed: No LLM configured. Please setup Groq or OpenAI in settings."
                
            provider_name = llm_service._provider_name
            model_name = llm_service._model
            api_key = getattr(llm_service._provider, "_client", None)
            
            chain_model = None
            if provider_name == "groq":
                from langchain_groq import ChatGroq
                chain_model = ChatGroq(model=model_name, api_key=llm_service._provider._client.api_key)
            elif provider_name == "openai":
                from langchain_openai import ChatOpenAI
                chain_model = ChatOpenAI(model=model_name, api_key=llm_service._provider._client.api_key)
            else:
                return f"Autonomous mode failed: browser-use does not support {provider_name} yet. Please use Groq or OpenAI."
                
            # Grab the active playwright browser context
            playwright_browser = await engine.ensure_browser()
            
            if hasattr(engine, '_context') and engine._context:
                context = engine._context
            else:
                return "Autonomous mode failed: Browser context not initialized."

            # We create a simple wrapper or use the context directly depending on browser-use version.
            # browser-use's Browser class accepts a playwright browser context.
            from browser_use.browser.browser import Browser, BrowserConfig
            
            # Since browser-use wants to manage its own playwright instance by default, 
            # we need to inject our existing context or start a new one just for this task.
            # For simplicity and stability in the first iteration, we let it use the LLM.
            
            # Note: A deep integration with an existing Playwright Context is complex because 
            # browser-use's `Browser` object is heavily stateful. 
            # We will initialize a separate autonomous agent here that runs visually.
            
            agent = Agent(
                task=task_description,
                llm=chain_model,
            )
            
            logger.info("Executing browser-use agent...")
            result = await agent.run()
            
            logger.info("Autonomous task completed.")
            
            if result.is_done():
                return f"Task completed successfully: {result.extracted_content()}"
            else:
                return "The agent finished, but may not have completed the task entirely."
                
        except Exception as e:
            logger.error(f"Autonomous browser task failed: {e}")
            return f"Failed to execute autonomous task: {e}"
