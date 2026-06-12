# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_data_files

datas_list = [
    ('automation/desktop/overlay.py', 'automation/desktop'),
    ('../voice/tts/models/*', 'voice/tts/models')
]
datas_list += collect_data_files('openwakeword')
datas_list += collect_data_files('av')
datas_list += collect_data_files('piper')

a = Analysis(
    ['run.py'],
    pathex=['.', '..'],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'app', 'automation', 'voice', 'uvicorn', 'fastapi', 'pydantic', 'sqlalchemy', 'loguru', 
        'aiosqlite', 'greenlet', 'supabase', 'dotenv', 'passlib.handlers.bcrypt', 'bcrypt', 
        'multipart', 'openwakeword', 'unittest',
        'app.services.llm.adapters.groq_adapter',
        'app.services.llm.adapters.openai_adapter',
        'app.services.llm.adapters.gemini_adapter',
        'app.services.llm.adapters.claude_adapter',
        'app.services.llm.adapters.deepseek_adapter',
        'app.services.llm.adapters.ollama_adapter'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'IPython', 'jupyter', 'tkinter', 'PySide6'],
    noarchive=False,
    optimize=0,
)

# Filter out massive CUDA and GPU binaries since Whisper is running on CPU
a.binaries = [b for b in a.binaries if not ('cublas' in b[0].lower() or 'cudnn' in b[0].lower() or 'curand' in b[0].lower())]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ace-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ace-backend'
)
