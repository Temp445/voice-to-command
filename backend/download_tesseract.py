import re
import urllib.request
import os
import subprocess

html = open('wiki.html', encoding='utf-8').read()
urls = re.findall(r'href=[\'\"](https://.*?tesseract-ocr-w64-setup.*?\.exe)[\'\"]', html)

if urls:
    url = urls[0]
    dest = "tesseract_installer.exe"
    print(f"Downloading Tesseract installer from {url}...")
    urllib.request.urlretrieve(url, dest)
    print("Download complete. Installing silently...")
    
    install_dir = r"e:\Nivin_Sync\ACE\Voice\Voice_Controller_v1\backend\automation\desktop\Tesseract-OCR"
    cmd = f'tesseract_installer.exe /VERYSILENT /DIR="{install_dir}"'
    subprocess.run(cmd, shell=True)
    print(f"Installed to {install_dir}")
else:
    print("No URL found")
