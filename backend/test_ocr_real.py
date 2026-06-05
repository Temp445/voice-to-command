import asyncio
import os
import tempfile
import mss
from PIL import Image

async def test_native_ocr():
    try:
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.globalization import Language
        from winsdk.windows.graphics.imaging import BitmapDecoder
        from winsdk.windows.storage import StorageFile
        
        engine = OcrEngine.try_create_from_language(Language("en-US"))
        if not engine:
            print("Engine failed")
            return
            
        temp_path = os.path.join(tempfile.gettempdir(), "ace_ocr_capture.bmp")
        print(f"Saving to {temp_path}")
        
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.save(temp_path, format="BMP")
            
        file = await StorageFile.get_file_from_path_async(os.path.abspath(temp_path))
        print(f"File loaded: {file}")
        
        stream = await file.open_async(0)
        print(f"Stream opened: {stream}")
        
        decoder = await BitmapDecoder.create_async(stream)
        print(f"Decoder created: {decoder}")
        
        bitmap = await decoder.get_software_bitmap_async()
        print(f"Bitmap loaded: {bitmap}")
        
        result = await engine.recognize_async(bitmap)
        print(f"Result lines: {len(result.lines)}")
        if len(result.lines) > 0:
            print(f"First line: {result.lines[0].text}")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test_native_ocr())
