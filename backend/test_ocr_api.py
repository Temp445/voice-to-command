import asyncio

async def test_ocr():
    try:
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.globalization import Language
        print("winsdk imported successfully")
        
        engine = OcrEngine.try_create_from_language(Language("en-US"))
        if engine:
            print("Engine created successfully")
        else:
            print("Engine creation failed")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_ocr())
