# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_data_files

datas_list = [
    ('automation/desktop/overlay.py', 'automation/desktop'),
    ('../voice/tts/models', 'voice/tts/models')
]
datas_list += collect_data_files('openwakeword')
datas_list += collect_data_files('av')

a = Analysis(
    ['run.py'],
    pathex=['.', '..'],
    binaries=[],
    datas=datas_list,
    hiddenimports=['app', 'automation', 'voice', 'uvicorn', 'fastapi', 'pydantic', 'sqlalchemy', 'loguru', 'aiosqlite', 'greenlet', 'supabase', 'dotenv', 'passlib.handlers.bcrypt', 'bcrypt', 'multipart', 'openwakeword'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ace-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
