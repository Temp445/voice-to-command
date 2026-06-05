import urllib.request
import zipfile
import os
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = "https://github.com/simonflueckiger/tesserocr-windows_build/releases/download/tesseract-5.2.0/tesseract-5.2.0-win64.zip"
dest = "tesseract.zip"
extract_dir = r"e:\Nivin_Sync\ACE\Voice\Voice_Controller_v1\backend\automation\desktop\Tesseract-OCR"

print(f"Downloading portable Tesseract from {url}...")
urllib.request.urlretrieve(url, dest)
print("Download complete. Extracting...")

os.makedirs(extract_dir, exist_ok=True)
with zipfile.ZipFile(dest, 'r') as zip_ref:
    zip_ref.extractall(extract_dir)

print(f"Extracted to {extract_dir}")
