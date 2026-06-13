"""
ACE Voice Controller — OCR Screen Controller
Uses Windows Native OCR (primary) or pytesseract (fallback) to find and click text on the screen.
"""

import os
import sys
import tempfile
import asyncio
import pytesseract
from PIL import Image
import mss
import pyautogui
from loguru import logger
from app.core.exceptions import AutomationError

# --- Setup Tesseract Path for Bundling Method (Fallback) ---
# If running in a PyInstaller bundle, point to the extracted temp folder.
# Otherwise, look in the local project directory "Tesseract-OCR", then default Windows path.
if getattr(sys, 'frozen', False):
    tess_dir = os.path.join(sys._MEIPASS, "Tesseract-OCR", "tesseract.exe")
else:
    tess_dir = os.path.join(os.path.dirname(__file__), "Tesseract-OCR", "tesseract.exe")

if os.path.exists(tess_dir):
    pytesseract.pytesseract.tesseract_cmd = tess_dir
else:
    DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(DEFAULT_TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_PATH

class OCRController:
    """Provides OCR capabilities to read and interact with on-screen text."""
    
    def __init__(self):
        # Allow fail-safe, but disable pause to keep it fast
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
    
    async def find_and_click_text(self, target_text: str) -> str:
        """Tries Windows Native OCR first, falls back to bundled Tesseract OCR."""
        target_text_lower = target_text.lower().strip()
        logger.info(f"Looking for text on screen: '{target_text}'")
        
        try:
            return await self._run_windows_native_ocr(target_text_lower)
        except Exception as e:
            logger.warning(f"Windows Native OCR failed or unavailable: {e}. Falling back to Tesseract.")
            return self._run_tesseract_ocr(target_text_lower, target_text)

    async def _run_windows_native_ocr(self, target_text_lower: str) -> str:
        """Uses Windows 10/11 built-in OCR via winsdk with a temporary file."""
        if sys.platform != "win32":
            raise Exception("Windows Native OCR is only available on Windows.")
            
        try:
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.globalization import Language
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.storage import StorageFile
        except ImportError:
            raise Exception("winsdk is not installed. Run 'pip install winsdk' for Native OCR.")
            
        engine = OcrEngine.try_create_from_language(Language("en-US"))
        if not engine:
            raise Exception("Windows OCR Engine not available for en-US language.")
            
        temp_path = os.path.join(tempfile.gettempdir(), "ace_ocr_capture.bmp")
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                # Save to temporary file as BMP (fastest compression for temporary reading)
                img.save(temp_path, format="BMP")
                
                # 0 = FileAccessMode.read
                file = await StorageFile.get_file_from_path_async(os.path.abspath(temp_path))
                stream = await file.open_async(0)
                
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                
                result = await engine.recognize_async(bitmap)
                
                for line in result.lines:
                    line_text = line.text.strip().lower()
                    
                    # Check if the target phrase exists anywhere in this full line
                    if target_text_lower in line_text:
                        # Find the first word in the line that forms part of the target phrase
                        for word in line.words:
                            word_text = word.text.strip().lower()
                            if word_text and word_text in target_text_lower:
                                x = word.bounding_rect.x + (word.bounding_rect.width / 2)
                                y = word.bounding_rect.y + (word.bounding_rect.height / 2)
                                
                                # Apply monitor offset if multiple monitors exist
                                x += monitor["left"]
                                y += monitor["top"]
                                
                                logger.info(f"Native OCR found phrase '{target_text_lower}' near '{word.text}' at ({x}, {y}). Clicking...")
                                pyautogui.moveTo(x, y, duration=0.2)
                                pyautogui.click()
                                return f"Clicked on '{target_text_lower}' using Windows Native OCR"
                            
                return f"Could not find '{target_text_lower}' on the screen using Native OCR."
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def _run_tesseract_ocr(self, target_text_lower: str, original_text: str) -> str:
        """Uses bundled Tesseract OCR."""
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img = img.convert('L')
                
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                for i in range(len(data['text'])):
                    word = data['text'][i].strip().lower()
                    
                    if word == target_text_lower or (len(target_text_lower) > 3 and target_text_lower in word):
                        x = data['left'][i] + (data['width'][i] / 2)
                        y = data['top'][i] + (data['height'][i] / 2)
                        
                        x += monitor["left"]
                        y += monitor["top"]
                        
                        logger.info(f"Tesseract found '{word}' at ({x}, {y}). Clicking...")
                        pyautogui.moveTo(x, y, duration=0.2)
                        pyautogui.click()
                        
                        return f"Clicked on '{original_text}' using Tesseract OCR"
                
                return f"Could not find '{original_text}' on the screen using Tesseract."
                
        except pytesseract.pytesseract.TesseractNotFoundError:
            logger.error("Tesseract OCR is not installed or bundled.")
            raise AutomationError("Tesseract OCR is missing and Native OCR failed. Please bundle Tesseract-OCR.")
        except Exception as e:
            logger.error(f"OCR Error: {e}")
            raise AutomationError(f"Failed to process screen OCR: {e}")
