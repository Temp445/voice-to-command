"""
ACE Voice Controller - Vision Service
Captures screen and prepares it for multimodal LLM processing.
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
