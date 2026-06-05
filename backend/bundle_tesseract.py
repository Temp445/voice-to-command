import urllib.request
import subprocess
import os
import shutil
import zipfile

def download_file(url, dest):
    req = urllib.request.Request(
        url, 
        data=None, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    )
    with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

# 1. Download innoextract
print("Downloading innoextract to unpack the installer without UAC...")
innoextract_url = "https://github.com/dscharrer/innoextract/releases/download/1.9/innoextract-1.9-windows.zip"
download_file(innoextract_url, "innoextract.zip")

with zipfile.ZipFile("innoextract.zip", 'r') as zip_ref:
    zip_ref.extractall("innoextract_bin")

# 2. Download latest Tesseract installer directly
installer_url = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
print(f"Downloading from {installer_url}...")
download_file(installer_url, "tesseract_installer.exe")

# 3. Extract the installer
print("Extracting Tesseract without running it...")
innoextract_exe = os.path.join("innoextract_bin", "innoextract.exe")
subprocess.run([innoextract_exe, "-e", "tesseract_installer.exe"])

# 4. Move to bundled directory
bundle_dir = r"e:\Nivin_Sync\ACE\Voice\Voice_Controller_v1\backend\automation\desktop\Tesseract-OCR"
if os.path.exists(bundle_dir):
    shutil.rmtree(bundle_dir)

print(f"Moving extracted files to {bundle_dir}...")
shutil.move("app", bundle_dir)

print("Bundling complete! Tesseract is now fully bundled inside your project.")
