# ACE Voice Controller v1

> AI-powered desktop voice control and automation system — your personal Jarvis.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | Tauri (Rust) |
| Frontend | Next.js 14 · React · TypeScript · Tailwind CSS |
| Backend | FastAPI · Python 3.11+ |
| Wake Word | OpenWakeWord (`"alexa"`) |
| STT | Faster-Whisper (offline) |
| TTS | Piper TTS (offline) or gTTS (Google Cloud) |
| Automation | pywinauto · pynput · psutil · Playwright |
| Database | Supabase (PostgreSQL) + SQLite (local cache) |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Rust + Cargo ([rustup.rs](https://rustup.rs))
- Visual Studio C++ Build Tools

### 1. Clone & Setup

```bash
cd Voice_Controller_v1
python scripts/setup.py
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Supabase URL + anon key
```

### 3. Run Database Migrations

Run `database/supabase_schema.sql` in your Supabase SQL editor.

### 4. Start Backend

```bash
cd backend
python -m app.main
# → FastAPI running at http://127.0.0.1:8000
# → API docs at http://127.0.0.1:8000/api/docs
```

### 5. Start Frontend (Dev)

```bash
cd frontend
npm install
npm run tauri:dev
# → Opens the desktop app window
```

### 6. Build Production .exe

```bash
cd frontend
npm run tauri:build
# → Generates: src-tauri/target/release/ace-voice-controller.exe
```

## Features

- 🎤 **Wake Word**: Say `"alexa"` to activate
- 📝 **STT**: Faster-Whisper offline transcription
- 🔊 **TTS**: Piper (offline) or Google Cloud TTS (select in Settings)
- 🖥️ **Desktop Automation**: Open/close apps, window management, file ops
- 🌐 **Browser Automation**: Playwright-powered Google/YouTube search
- ⌨️ **Input Control**: pynput keyboard + mouse automation
- 💾 **Database**: Supabase + SQLite local cache
- 🔒 **Auth**: Supabase email/password auth
- 🎨 **UI**: Glassmorphism dark UI with animated voice orb

## Command Examples

| Say or Type | Action |
|-------------|--------|
| `open notepad` | Launches Notepad |
| `search google for python` | Opens Google search |
| `open youtube.com` | Opens YouTube |
| `volume up` | Increases volume |
| `take a screenshot` | Saves screenshot to Desktop |
| `lock screen` | Locks Windows |
| `open folder downloads` | Opens Downloads in Explorer |

## Project Structure

```
Voice_Controller_v1/
├── backend/       FastAPI server + services + DB models
├── voice/         Wake word · STT · TTS pipeline
├── automation/    Desktop · browser · input automation
├── services/      Background service + system tray
├── database/      SQL schema for Supabase
├── frontend/      Tauri + Next.js desktop UI
├── scripts/       Setup + model download + build scripts
└── shared/        Shared utilities + types
```



