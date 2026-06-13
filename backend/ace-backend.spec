# -*- mode: python ; coding: utf-8 -*-
# ACE Voice Controller — Optimized PyInstaller Build Spec
# Optimizations applied:
#   - UPX disabled: eliminates 5-10s decompression delay on every launch
#   - Aggressive exclusions: strips unused ML, UI, and dev-tool libraries (~500MB+ saved)
#   - Extended binary filter: removes unused GPU, ONNX, and non-Chromium Playwright binaries
#   - optimize=2: strips docstrings and assertions from bundled .pyc files (~5% size reduction)

from PyInstaller.utils.hooks import collect_data_files

datas_list = [
    ('automation/desktop/overlay.py', 'automation/desktop'),
    ('../voice/tts/models', 'voice/tts/models'),
    ('../.env', '.')
]
datas_list += collect_data_files('openwakeword')
datas_list += collect_data_files('av')
datas_list += collect_data_files('piper')
datas_list += collect_data_files('playwright_stealth')

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
    excludes=[
        # --- Dev tools (never needed in production) ---
        'matplotlib', 'pandas', 'IPython', 'jupyter', 'notebook',
        'nbformat', 'nbconvert', 'ipykernel', 'ipywidgets',
        # --- UI frameworks (not used in headless backend) ---
        'tkinter', 'PySide6',
        'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
        # --- Massive ML frameworks (not used; pulled in by transitive deps) ---
        'torch', 'torchvision', 'torchaudio',
        'tensorflow', 'tensorboard', 'keras',
        'sklearn', 'scipy',
        # --- gRPC (pulled in by google-generativeai but not needed at runtime) ---
        'grpc', '_grpc', 'grpcio',
        # --- Unused test/debug utilities ---
        'pytest', 'unittest.mock', 'doctest',
    ],
    noarchive=False,
    optimize=2,  # Strip docstrings + assertions from .pyc files
)

# ── Binary filter: remove unused GPU and non-Chromium Playwright binaries ─────
_EXCLUDE_BINARY_FRAGMENTS = [
    'cublas', 'cudnn', 'curand',          # CUDA (we run Whisper on CPU)
    'onnxruntime_gpu',                     # GPU ONNX runtime
    'playwright-webkit', 'playwright-firefox',  # We only use Chromium
    'cufile', 'nvfatbin', 'nvjitlink',    # NVIDIA JIT linker (never needed)
]
a.binaries = [
    b for b in a.binaries
    if not any(frag in b[0].lower() for frag in _EXCLUDE_BINARY_FRAGMENTS)
]

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
    upx=False,   # DISABLED: UPX forces Windows to decompress all DLLs on every launch (+5-10s startup)
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
    upx=False,   # DISABLED: see above
    upx_exclude=[],
    name='ace-backend'
)
