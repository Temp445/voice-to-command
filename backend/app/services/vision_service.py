"""
ACE Voice Controller - Vision Service
Captures screen and prepares it for multimodal LLM processing.

v2 additions:
  - find_and_click_by_voice(): takes a screenshot, asks Gemini Vision what element
    to interact with, and returns a structured action that command_service can execute.
  - snapshot_page_as_base64(): returns a Playwright screenshot (browser viewport only)
    for more accurate page-level vision — faster than full-screen mss capture.
"""

import base64
import io
from loguru import logger
from app.core.exceptions import AutomationError


class VisionService:
    @staticmethod
    def capture_screen_base64(quality: int = 80) -> str:
        """
        Captures the primary monitor using mss and returns it as a Base64-encoded WebP string.
        WebP is used for high compression while maintaining OCR-readable quality.
        """
        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                # monitor 1 is usually the primary display.
                # monitor 0 is a bounding box of all monitors combined.
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor)

                # Convert to PIL Image
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                # Save to in-memory byte buffer as WebP
                buffer = io.BytesIO()
                img.save(buffer, format="WEBP", quality=quality)
                buffer.seek(0)

                # Encode to Base64
                img_b64 = base64.b64encode(buffer.read()).decode("utf-8")
                logger.info(f"Screen captured and encoded (WebP, quality={quality})")
                return img_b64

        except ImportError:
            logger.error("Missing required vision dependencies: mss or Pillow.")
            raise AutomationError("Please install mss and Pillow to use Vision capabilities.")
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            raise AutomationError(f"Screen capture failed: {e}")

    @staticmethod
    async def snapshot_browser_page_base64(quality: int = 80) -> str | None:
        """
        Takes a Playwright screenshot of the active browser page (viewport only).
        Much faster than full-screen mss capture and more focused on what the user sees.
        Returns Base64-encoded WebP, or None if the browser isn't open.
        """
        try:
            from automation.browser.browser_engine import BrowserEngine, _run_in_playwright

            engine = BrowserEngine()
            if engine._context is None:
                return None

            async def _screenshot():
                page = await engine.get_active_page()
                if not page:
                    return None
                raw = await page.screenshot(type="jpeg", quality=quality, full_page=False)
                return base64.b64encode(raw).decode("utf-8")

            return await _run_in_playwright(_screenshot())
        except Exception as e:
            logger.debug(f"Browser page screenshot failed: {e}")
            return None

    @staticmethod
    async def describe_screen(query: str = "Describe what is currently visible on my screen.") -> str:
        """Captures the screen and uses Gemini Vision to describe it."""
        try:
            b64_image = VisionService.capture_screen_base64()
            from app.config import settings
            from app.services.llm.adapters.gemini_adapter import GeminiAdapter
            
            adapter = GeminiAdapter(api_key=settings.gemini_api_key, model="gemini-1.5-pro")
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant analyzing the user's desktop screen. Be concise and precise."},
                {"role": "user", "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{b64_image}"}}
                ]}
            ]
            response = await adapter.chat(messages)
            return response
        except Exception as e:
            logger.error(f"Failed to describe screen: {e}")
            return f"I couldn't analyze the screen: {e}"

    @staticmethod
    async def find_and_click_by_voice(command: str) -> dict | None:
        """
        Vision Fallback (Layer 3.5): When all text-based matching fails, capture the
        browser page as an image and ask the configured LLM (Gemini preferred) to
        identify WHAT should be clicked/typed for the given voice command.

        Returns a structured action dict:
          {
            "action":      "click" | "type" | "scroll" | "none",
            "target_text": "Button label or field name to interact with",
            "value":       "Text to type (only for 'type' action)",
            "confidence":  0.0–1.0
          }
        or None if vision is unavailable or LLM didn't return a valid action.
        """
        try:
            # Try browser viewport first (faster, more focused)
            b64_image = await VisionService.snapshot_browser_page_base64(quality=75)
            mime_type = "image/jpeg"

            if not b64_image:
                # Fall back to full-screen mss capture
                try:
                    b64_image = VisionService.capture_screen_base64(quality=70)
                    mime_type = "image/webp"
                except Exception:
                    logger.debug("Vision fallback: both browser snapshot and mss capture failed.")
                    return None

            from app.services.llm.llm_service import llm_service
            if not llm_service.is_ready:
                return None

            vision_prompt = (
                f"The user said: \"{command}\"\n\n"
                "Look at the screenshot. What single UI action should be performed to fulfill this command?\n\n"
                "Reply with ONLY a valid JSON object (no markdown, no explanation):\n"
                '{"action":"click|type|scroll|none","target_text":"visible label of element to interact with","value":"text to type if action=type, else empty string","confidence":0.0}\n\n'
                "Rules:\n"
                "- action=click: when user wants to press a button, link, tab, or checkbox\n"
                "- action=type: when user wants to fill a text field (include the text in 'value')\n"
                "- action=scroll: when user wants to scroll up/down\n"
                "- action=none: if no clear UI element matches the command\n"
                "- target_text must be the EXACT visible text label of the element on screen\n"
                "- confidence: 0.0–1.0 (how certain you are)"
            )

            import asyncio
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}}
                    ]
                }
            ]

            # Use Gemini adapter directly for vision (it supports multimodal)
            try:
                from app.config import settings
                from app.services.llm.adapters.gemini_adapter import GeminiAdapter
                import json as _json

                adapter = GeminiAdapter(
                    api_key=settings.gemini_api_key,
                    model="gemini-2.0-flash"  # fast multimodal model
                )
                raw = await asyncio.wait_for(
                    adapter.chat(messages, temperature=0.0, max_tokens=120),
                    timeout=4.0
                )
            except Exception:
                # If Gemini adapter isn't directly available, use llm_service provider
                try:
                    raw = await asyncio.wait_for(
                        llm_service._provider.chat(messages, temperature=0.0, max_tokens=120),
                        timeout=4.0
                    )
                except Exception as e2:
                    logger.debug(f"Vision LLM call failed: {e2}")
                    return None

            # Parse the JSON response
            import json as _json
            import re as _re
            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            # Extract JSON object from the response
            _json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
            if not _json_match:
                return None
            action_dict = _json.loads(_json_match.group(0))

            # Validate minimum required fields
            if not action_dict.get("action") or not action_dict.get("target_text"):
                return None
            if action_dict["action"] == "none" or float(action_dict.get("confidence", 0)) < 0.5:
                return None

            logger.info(
                f"Vision fallback: '{command}' → action={action_dict['action']} "
                f"target='{action_dict['target_text']}' confidence={action_dict.get('confidence', '?')}"
            )
            return action_dict

        except Exception as e:
            logger.debug(f"Vision fallback find_and_click_by_voice failed: {e}")
            return None


# Singleton-style access
vision_service = VisionService()
