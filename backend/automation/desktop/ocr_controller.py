"""
ACE Voice Controller — OCR Screen Controller
Uses mss, Pillow, and pytesseract to find and click text on the screen.
"""

import pytesseract
from PIL import Image
import mss
import pyautogui
from loguru import logger
import io
import time
from app.core.exceptions import AutomationError

class OCRController:
    """Provides OCR capabilities to read and interact with on-screen text."""
    
    def __init__(self):
        # Allow fail-safe, but disable pause to keep it fast
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
    
    def find_and_click_text(self, target_text: str) -> str:
        """Takes a screenshot, finds the target text, and clicks its center coordinates."""
        target_text_lower = target_text.lower().strip()
        logger.info(f"Looking for text on screen: '{target_text}'")
        
        try:
            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                
                # Convert to PIL Image and preprocess (grayscale)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img = img.convert('L')
                
                # Run OCR to get bounding boxes
                # output_type=dict returns a dictionary with 'text', 'left', 'top', 'width', 'height', etc.
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                # Iterate through detected words
                for i in range(len(data['text'])):
                    word = data['text'][i].strip().lower()
                    
                    # If we find a match, click the center of the bounding box
                    if word == target_text_lower or (len(target_text_lower) > 3 and target_text_lower in word):
                        x = data['left'][i] + (data['width'][i] / 2)
                        y = data['top'][i] + (data['height'][i] / 2)
                        
                        # Apply monitor offset if multiple monitors exist
                        x += monitor["left"]
                        y += monitor["top"]
                        
                        logger.info(f"Found '{word}' at ({x}, {y}). Clicking...")
                        pyautogui.moveTo(x, y, duration=0.2)
                        pyautogui.click()
                        
                        return f"Clicked on '{target_text}'"
                
                # If not found
                return f"Could not find '{target_text}' on the screen."
                
        except pytesseract.pytesseract.TesseractNotFoundError:
            logger.error("Tesseract OCR is not installed or not in PATH.")
            raise AutomationError(
                "Tesseract OCR is missing. Please download and install Tesseract OCR for Windows, "
                "and ensure it is added to your system PATH."
            )
        except Exception as e:
            logger.error(f"OCR Error: {e}")
            raise AutomationError(f"Failed to process screen OCR: {e}")
