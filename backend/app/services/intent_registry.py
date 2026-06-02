"""
ACE Voice Controller — Command Intent Registry
Defines all built-in intents with regex patterns and wires them to the automation executor.
"""

import re
from app.services.command_service import Intent, command_service
from loguru import logger


# ─── Lazy import executor to avoid circular deps ─────────────────────────────
async def _get_executor():
    from automation.executor import ActionExecutor
    return ActionExecutor()


# ─── Intent Handlers ─────────────────────────────────────────────────────────

async def handle_open_app(app: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    ctrl = AppController()
    return await ctrl.open_application(app.strip())


async def handle_close_app(app: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    return await AppController().close_application(app.strip())


async def handle_close_heavy_apps(**_) -> str:
    from automation.desktop.app_controller import AppController
    return await AppController().close_heavy_applications(threshold_mb=500)


async def handle_search_google(query: str = "", browser: str | None = None, **_) -> str:
    from automation.browser.search import BrowserSearch
    return await BrowserSearch().google(query.strip(), browser)


async def handle_search_youtube(query: str = "", **_) -> str:
    from automation.browser.search import BrowserSearch
    return await BrowserSearch().youtube(query.strip())


async def handle_open_website(url: str = "", **_) -> str:
    from automation.ace_browser.ace_browser_controller import ACEBrowserController as BrowserController
    bc = BrowserController()
    url = url.strip()
    if not url:
        return "Please specify a website to open."
    # Append .com if it's just a raw name without domain or protocol
    if "." not in url and not url.startswith("http"):
        url = url + ".com"
    await bc.navigate(url)
    return f"Opened {url}"

async def handle_browser_play_pause(**_) -> str:
    from automation.ace_browser.ace_browser_controller import ACEBrowserController as BrowserController
    return await BrowserController().play_pause()

async def handle_browser_go_back(**_) -> str:
    from automation.ace_browser.ace_browser_controller import ACEBrowserController as BrowserController
    return await BrowserController().go_back()

async def handle_browser_click_first_result(**_) -> str:
    from automation.ace_browser.ace_browser_controller import ACEBrowserController as BrowserController
    return await BrowserController().click_first_result()

async def handle_read_page_title(**_) -> str:
    from automation.ace_browser.ace_browser_controller import ACEBrowserController as BrowserController
    title = await BrowserController().get_page_title()
    return f"The page title is: {title}"

async def handle_extract_page_content(**_) -> str:
    from automation.ace_browser.ace_browser_controller import ACEBrowserController as BrowserController
    content = await BrowserController().extract_page_content()
    # If content is huge, trim it for TTS
    if len(content) > 500:
        content = content[:500] + "... [Content truncated]"
    return f"Here is the page content:\n{content}"
async def handle_analyze_screen(query: str = "", **_) -> str:
    from app.services.vision_service import VisionService
    if not query:
        query = "Describe what is currently visible on my screen."
    return await VisionService.describe_screen(query)

async def handle_open_folder(path: str = "", disambiguation: str | None = None, **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().open_folder(path.strip(), disambiguation)


async def handle_close_folder(path: str = "", **_) -> str:
    from automation.desktop.window_manager import WindowManager
    folder_name = path.strip()
    if WindowManager().close_window_by_title(folder_name):
        return f"Closed folder: {folder_name}"
    return f"Folder '{folder_name}' is not currently open."


async def handle_open_project(project_name: str = "", **_) -> str:
    from app.services.context_state import get_context
    import subprocess
    import os
    
    clean = project_name.replace("project", "").strip()
    
    # 1. Try to fetch from explicit projects.json mapping
    ctx = get_context()
    project_path = ctx.get_project_path(clean)
    
    if not project_path:
        # 2. Fallback to Windows Search API
        from automation.desktop.file_indexer import get_indexer
        indexer = get_indexer()
        results = indexer.search(clean, is_folder=True, limit=5)
        if results:
            project_path = results[0]["path"]
            
    if not project_path:
        return f"Could not find a project folder named {clean}"
        
    ctx.set("active_project_path", project_path)
    
    # Open in VS Code (assuming code is in PATH)
    try:
        subprocess.Popen(["code", project_path], cwd=project_path, shell=True)
        return f"Opened project '{clean}' in VS Code"
    except Exception as e:
        return f"Found project but failed to open in VS Code: {e}"


async def handle_create_project(project_type: str = "", project_name: str = "", **_) -> str:
    from app.services.context_manager import context_manager
    import subprocess
    import os
    
    # Clean inputs
    project_type = project_type.lower().strip() if project_type else ""
    project_name = project_name.lower().strip() if project_name else "my-app"
    project_name = project_name.replace(" ", "-") # normalize for npm
    
    desktop = os.path.expanduser("~/Desktop")
    target_path = os.path.join(desktop, project_name)
    
    original_project_name = project_name
    counter = 1
    while os.path.exists(target_path):
        project_name = f"{original_project_name}-{counter}"
        target_path = os.path.join(desktop, project_name)
        counter += 1
    # Determine scaffolding command
    if "react" in project_type or "vite" in project_type:
        scaffold_cmd = f"npm create vite@latest {project_name} --yes -- --template react"
        post_cmd = "npm install"
    elif "next" in project_type:
        scaffold_cmd = f"npx create-next-app@latest {project_name} --yes --use-npm --eslint --tailwind --app"
        post_cmd = "" # Next.js does npm install automatically
    else:
        # Generic fallback
        scaffold_cmd = f"mkdir {project_name}"
        post_cmd = ""
        
    try:
        # 1. Run the fast scaffold command
        # 2. IMMEDIATELY open VS Code so the user isn't waiting
        # 3. CD into the directory and run the slow `npm install` (so the user has a fully working project)
        full_cmd = f"echo Scaffolding {project_type} project (downloading template)... && {scaffold_cmd} && echo Opening VS Code... && code {project_name}"
        if post_cmd:
            full_cmd += f" && echo. && echo Installing dependencies from npm (this may take 2-5 minutes depending on network)... && cd {project_name} && {post_cmd}"
            
        full_cmd += " && echo. && echo Finished! You can now close this terminal."
        
        # Spawn terminal to show progress
        subprocess.Popen(f"start cmd /k \"cd /d {desktop} && {full_cmd}\"", shell=True)
        
        # Track context
        context_manager.last_project_path = target_path
        
        return f"Creating a new {project_type} project named {project_name} on your Desktop..."
    except Exception as e:
        return f"Failed to create project: {e}"


async def handle_run_dev_server(cmd: str = "", **_) -> str:
    from app.services.context_manager import context_manager
    import subprocess
    import os
    
    if not context_manager.last_project_path:
        return "I don't know which project to run. Please open a project first."
        
    project_path = context_manager.last_project_path
    
    # Simple detection logic
    if os.path.exists(os.path.join(project_path, "package.json")):
        start_cmd = "npm run dev"
        context_manager.last_dev_server_url = "http://localhost:3000"
    elif os.path.exists(os.path.join(project_path, "requirements.txt")) or os.path.exists(os.path.join(project_path, "main.py")):
        start_cmd = "python main.py" # Simple fallback
        context_manager.last_dev_server_url = "http://localhost:8000"
    else:
        start_cmd = cmd or "npm start"
        
    try:
        # We spawn in a new console window so the user can see the dev server
        subprocess.Popen(f"start cmd /k \"cd /d {project_path} && {start_cmd}\"", shell=True)
        return f"Started dev server in {os.path.basename(project_path)}"
    except Exception as e:
        return f"Failed to start dev server: {e}"


async def handle_open_dev_server(**_) -> str:
    from app.services.context_manager import context_manager
    from automation.ace_browser.ace_browser_controller import ACEBrowserController as BrowserController
    
    url = context_manager.last_dev_server_url
    if not url:
        return "I don't have a dev server URL tracked in context."
        
    bc = BrowserController()
    await bc.navigate(url)
    return f"Opened application in browser at {url}"


async def handle_search_file(file_name: str = "", **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().search_file(file_name.strip())


async def handle_create_folder(folder_name: str = "", drive: str | None = None, **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().create_folder(folder_name.strip(), drive)


async def handle_run_command(cmd: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    return await AppController().run_terminal_command(cmd.strip())


async def handle_volume_up(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().volume_up()
    return "Volume increased"


async def handle_volume_down(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().volume_down()
    return "Volume decreased"


async def handle_mute(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().mute()
    return "Muted"


async def handle_minimize_window(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    WindowManager().minimize_active()
    return "Window minimized"


async def handle_maximize_window(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    WindowManager().maximize_active()
    return "Window maximized"


async def handle_minimize_app(app: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    from automation.desktop.window_manager import WindowManager
    import pywinauto
    
    clean = app.strip()
    candidates = AppController()._resolve_candidates(clean.lower())
    
    for exe in candidates:
        try:
            win_app = pywinauto.Application(backend="uia").connect(path=exe, timeout=1)
            win_app.top_window().minimize()
            return f"Minimized {clean}"
        except Exception:
            pass

    if WindowManager().minimize_by_title(clean):
        return f"Minimized {clean}"
    return f"Could not find open window for {clean}"


async def handle_save(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().press_enter()
    return "Saving..."


async def handle_dont_save(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    from pynput.keyboard import Key
    KeyboardController().press(Key.alt, 'n')
    return "Changes discarded."


async def handle_cancel(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().press_escape()
    return "Canceled."


async def handle_maximize_app(app: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    from automation.desktop.window_manager import WindowManager
    import pywinauto
    
    clean = app.strip()
    candidates = AppController()._resolve_candidates(clean.lower())
    
    for exe in candidates:
        try:
            win_app = pywinauto.Application(backend="uia").connect(path=exe, timeout=1)
            win_app.top_window().maximize()
            return f"Maximized {clean}"
        except Exception:
            pass

    if WindowManager().maximize_by_title(clean):
        return f"Maximized {clean}"
    return f"Could not find open window for {clean}"


async def handle_close_window(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    WindowManager().close_active()
    return "Window closed"


async def handle_clipboard_copy(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().copy()
    return "Copied to clipboard"


async def handle_clipboard_paste(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().paste()
    return "Pasted from clipboard"


async def handle_screenshot(**_) -> str:
    from automation.system.clipboard import ClipboardManager
    path = ClipboardManager().screenshot()
    return f"Screenshot saved to {path}"


async def handle_system_sleep(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().sleep()
    return "System going to sleep"


async def handle_system_shutdown(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().shutdown()
    return "System shutting down"


async def handle_system_restart(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().restart()
    return "System restarting"


async def handle_type_text(text: str = "", app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    if app_name:
        from automation.desktop.window_manager import WindowManager
        WindowManager().focus_by_title(app_name)
    import asyncio; await asyncio.sleep(0.5)
    KeyboardController().type_text(text.strip())
    return f"Typed: {text}{f' in {app_name}' if app_name else ''}"


async def handle_lock_screen(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().lock_screen()
    return "Screen locked"


async def handle_click(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().click()
    return "Clicked"


async def handle_double_click(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().double_click()
    return "Double clicked"

async def handle_click_text(text: str = "", **_) -> str:
    from automation.desktop.ocr_controller import OCRController
    return OCRController().find_and_click_text(text.strip())


async def handle_right_click(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().right_click()
    return "Right clicked"


async def handle_scroll_up(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().scroll_up()
    return "Scrolled up"


async def handle_scroll_down(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().scroll_down()
    return "Scrolled down"


async def handle_submit(app_name: str = "", **_) -> str:
    import asyncio
    import pywinauto
    from automation.desktop.window_manager import WindowManager
    from automation.input.keyboard_controller import KeyboardController

    typed_via_pywinauto = False
    if app_name:
        try:
            win = WindowManager()._find_window_by_title(app_name)
            if win:
                app = pywinauto.Application(backend="uia").connect(process=win.process_id())
                top_win = app.top_window()
                top_win.set_focus()
                top_win.type_keys("{ENTER}")
                typed_via_pywinauto = True
        except Exception:
            pass
            
    if not typed_via_pywinauto:
        if app_name:
            WindowManager().focus_by_title(app_name)
        await asyncio.sleep(0.5)
        KeyboardController().press_enter()
        
    return f"Submitted {f'in {app_name}' if app_name else ''}"


async def handle_dont_save(app_name: str = "", **_) -> str:
    if app_name:
        from automation.desktop.app_controller import AppController
        await AppController().close_application(app_name, force=True)
        return f"Closed {app_name} without saving"
    else:
        from automation.input.keyboard_controller import KeyboardController
        KeyboardController().press("n")
        return "Pressed Don't Save"


async def handle_save(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    if app_name:
        from automation.desktop.window_manager import WindowManager
        WindowManager().focus_by_title(app_name)
    import asyncio; await asyncio.sleep(0.5)
    KeyboardController().save()
    return f"PENDING_FILENAME: Pressed Save{f' in {app_name}' if app_name else ''}. What should I name the file?"


async def handle_set_filename(text: str = "", app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    import asyncio
    import pywinauto
    from automation.desktop.window_manager import WindowManager
    
    typed_via_pywinauto = False
    top_win = None
    
    try:
        desktop = pywinauto.Desktop(backend="win32")
        
        # 1. Check if a Save dialog is ALREADY open
        dialogs = [w for w in desktop.windows() if w.window_text() in ("Save As", "Save", "Open", "Confirm Save As")]
        
        # 2. If not open, trigger it (handles one-shot commands like "save the file as demo44")
        if not dialogs:
            if app_name:
                WindowManager().focus_by_title(app_name)
            KeyboardController().save() # Presses Ctrl+S
            await asyncio.sleep(0.5)
            
        # 3. Poll for up to 1.5 seconds to allow the dialog to spawn
        for _ in range(15):
            dialogs = [w for w in desktop.windows() if w.window_text() in ("Save As", "Save", "Open", "Confirm Save As")]
            if dialogs:
                break
            await asyncio.sleep(0.1)
            
        if dialogs:
            top_win = dialogs[0]
            top_win.set_focus()
            top_win.type_keys(text.strip() + "{ENTER}", with_spaces=True)
            typed_via_pywinauto = True
        elif app_name:
            # Fallback to application's top window via uia if no explicit dialog is found
            win = WindowManager()._find_window_by_title(app_name)
            if win:
                app = pywinauto.Application(backend="uia").connect(process=win.process_id())
                top_win = app.top_window()
                top_win.set_focus()
                top_win.type_keys(text.strip() + "{ENTER}", with_spaces=True)
                typed_via_pywinauto = True
    except Exception as e:
        pass
            
    if not typed_via_pywinauto:
        # Fallback to physical keyboard if pywinauto failed
        if app_name:
            WindowManager().focus_by_title(app_name)
        await asyncio.sleep(0.5)
        KeyboardController().type_text(text.strip())
        await asyncio.sleep(0.3)
        KeyboardController().press_enter()
        
    await asyncio.sleep(0.8) # Wait for potential conflict dialog to appear
    
    # Check for conflict dialog
    conflict_found = False
    try:
        # Check if a "Confirm Save As" dialog popped up
        desktop = pywinauto.Desktop(backend="win32")
        conflict_dialogs = [w for w in desktop.windows() if "confirm save as" in w.window_text().lower()]
        if conflict_dialogs:
            conflict_found = True
            top_win = conflict_dialogs[0]
            
        if not conflict_found and app_name and top_win:
            # Re-fetch top window in case a new modal appeared in UIA
            app = pywinauto.Application(backend="uia").connect(process=win.process_id())
            new_top = app.top_window()
            title = new_top.window_text().lower()
            if "confirm" in title or "already exists" in title or "replace" in title:
                conflict_found = True
    except Exception:
        pass
        
    if conflict_found:
        KeyboardController().press_escape() # Cancel the conflict dialog
        return f"PENDING_FILENAME: A file named '{text}' already exists. Please tell me a different file name."
        
    return f"File saved as '{text}'."

async def handle_cancel(app_name: str = "", **_) -> str:
    import asyncio
    import pywinauto
    from automation.desktop.window_manager import WindowManager
    from automation.input.keyboard_controller import KeyboardController

    typed_via_pywinauto = False
    
    try:
        # 1. Try to find common Win32 dialogs globally (Save As, Open, Confirm, Notepad warnings)
        desktop = pywinauto.Desktop(backend="win32")
        # Notepad warning dialog is usually titled "Notepad"
        dialogs = [w for w in desktop.windows() if w.window_text() in ("Save As", "Open", "Confirm Save As", "Notepad", app_name, app_name.title())]
        
        if dialogs:
            # Sort by window area to find the smallest one (dialogs are smaller than main apps)
            dialogs.sort(key=lambda w: w.rectangle().width() * w.rectangle().height())
            top_win = dialogs[0]
            top_win.set_focus()
            top_win.type_keys("{ESC}")
            typed_via_pywinauto = True
            
        if not typed_via_pywinauto and app_name:
            # 2. Fallback to UIA top window of the process
            win = WindowManager()._find_window_by_title(app_name)
            if win:
                app = pywinauto.Application(backend="uia").connect(process=win.process_id())
                top_win = app.top_window()
                top_win.set_focus()
                top_win.type_keys("{ESC}")
                typed_via_pywinauto = True
    except Exception:
        pass
            
    if not typed_via_pywinauto:
        if app_name:
            WindowManager().focus_by_title(app_name)
        await asyncio.sleep(0.5)
        KeyboardController().press_escape()
        
    return f"Canceled {f'in {app_name}' if app_name else ''}"


async def handle_ask_llm(question: str = "", **_) -> str:
    from app.services.llm.llm_service import llm_service
    question = question.strip()
    if not llm_service.is_ready:
        return "AI assistant is not configured. Please go to Settings → AI Assistant to set up a provider."
    return await llm_service.chat(question)


async def handle_ask_and_type(question: str = "", **_) -> str:
    """Ask the LLM to draft content, then physically type it via the keyboard."""
    from app.services.llm.llm_service import llm_service
    from automation.input.keyboard_controller import KeyboardController
    question = question.strip()
    if not llm_service.is_ready:
        return "AI assistant is not configured. Please go to Settings → AI Assistant."
    generated = await llm_service.chat(question)
    KeyboardController().type_text(generated)
    return f"Drafted and typed: {generated[:80]}{'...' if len(generated) > 80 else ''}"


async def handle_vscode_terminal(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    from automation.input.keyboard import KeyboardController
    import asyncio
    
    # Try to focus VS Code
    if WindowManager().focus_by_title("Visual Studio Code"):
        await asyncio.sleep(0.5)
        # Ctrl + ` shortcut
        KeyboardController().press_keys(["ctrl", "`"])
        return "Opened VS Code terminal."
    return "Could not find an active VS Code window."

# ─── Register All Intents ────────────────────────────────────────────────────

def register_all_intents() -> None:
    """Call this once at startup to wire up all built-in command intents."""

    intents = [
        Intent(
            name="search_youtube",
            patterns=[
                r"(?:search|find|play)\s+(?P<query>.+)\s+on youtube",
                r"(?:open\s+)?youtube\s+(?:and\s+)?(?:search|find|play)\s+(?:for\s+)?(?P<query>.+)",
                r"(?:search|find|play)\s+(?:on\s+)?youtube\s+(?:for\s+)?(?P<query>.+)",
                r"youtube\s+(?P<query>.+)",
            ],
            handler=handle_search_youtube,
            description="Search YouTube in the browser",
            examples=["search lofi music on youtube", "youtube python tutorial"],
            param_names=["query"],
        ),
        Intent(
            name="search_google",
            patterns=[
                r"(?:open\s+)?(?P<browser>edge|chrome|firefox)?\s*(?:and\s+)?(?:search|find|look up)\s+(?:for\s+)?(?P<query>.+)",
                r"(?:open\s+)?(?P<browser>edge|chrome|firefox)?\s*(?:and\s+)?google\s+(?:for\s+)?(?P<query>.+)",
                r"(?:search|google)\s+(?:for\s+)?(?P<query>.+)",
                r"(?:look up|find)\s+(?P<query>.+)\s+on google",
            ],
            handler=handle_search_google,
            description="Search Google in the browser",
            examples=["search for python tutorials", "google the weather", "open edge search spiderman"],
            param_names=["query", "browser"],
        ),
        Intent(
            name="open_website",
            patterns=[
                r"(?:open|go to|visit|navigate to)\s+(?P<url>(?:https?://)?[\w\-\.]+\.\w{2,}(?:/\S*)?)",
                r"(?:open|go to|visit)\s+(?P<url>youtube|google|github|netflix|spotify|twitter|facebook|gmail|amazon|reddit|linkedin)"
            ],
            handler=handle_open_website,
            description="Open a website URL in the browser",
            examples=["open github.com", "go to youtube.com", "visit google.com"],
            param_names=["url"],
        ),
        Intent(
            name="browser_play_pause",
            patterns=[
                r"(?:play|pause)\s+(?:the\s+)?(?:video|music|song)",
            ],
            handler=handle_browser_play_pause,
            description="Play or pause media in the browser",
            examples=["play the video", "pause music"],
        ),
        Intent(
            name="browser_go_back",
            patterns=[
                r"go\s+back",
                r"previous\s+page",
            ],
            handler=handle_browser_go_back,
            description="Navigate back in the browser",
            examples=["go back", "go to previous page"],
        ),
        Intent(
            name="browser_click_first_result",
            patterns=[
                r"(?:click|open)\s+(?:the\s+)?first\s+(?:result|video|link)",
            ],
            handler=handle_browser_click_first_result,
            description="Click the first search result in the browser",
            examples=["open the first result", "play the first video"],
        ),
        Intent(
            name="read_page_title",
            patterns=[
                r"(?:what is|read|get)\s+(?:the\s+)?page\s+title",
                r"what page am i on",
                r"read\s+title"
            ],
            handler=handle_read_page_title,
            description="Read the title of the current webpage",
            examples=["what is the page title", "read the page title"],
        ),
        Intent(
            name="extract_page_content",
            patterns=[
                r"(?:extract|read|get)\s+(?:the\s+)?(?:page\s+)?content",
                r"(?:extract|read|get)\s+(?:the\s+)?(?:page\s+)?text",
                r"what does this page say"
            ],
            handler=handle_extract_page_content,
            description="Extract readable text from the current webpage",
            examples=["extract the page content", "read the page text"],
        ),
        Intent(
            name="analyze_screen",
            patterns=[
                r"(?:what\s+is|what's|describe)\s+(?:on\s+)?(?:my\s+)?screen",
                r"read\s+(?:the\s+)?(?:my\s+)?screen",
            ],
            handler=handle_analyze_screen,
            description="Use AI vision to describe what is currently on the screen",
            examples=["what is on my screen?", "read my screen"],
        ),
        Intent(
            name="open_folder",
            patterns=[
                # "open folder <name>" or "open directory <name>" — keyword FIRST (highest priority)
                r"open\s+(?:the\s+)?(?:folder|directory)\s+(?P<path>.+)",
                # "show me <name> folder"
                r"show\s+(?:me\s+)?(?:the\s+)?(?P<path>[\w\s]+?)\s+(?:folder|directory)",
                # "open <name> folder" — keyword at END; guard ensures path doesn't start with 'folder'
                r"open\s+(?:the\s+)?(?P<path>(?!folder\b|directory\b)[\w\s]+?)\s+(?:folder|directory)",
                # "go to downloads", "go to documents"
                r"go\s+to\s+(?P<path>downloads|documents|desktop|pictures|music|videos|home)",
            ],
            handler=handle_open_folder,
            description="Open a folder in Windows Explorer",
            examples=["open the payroll folder", "open folder downloads", "show me documents folder"],
            param_names=["path"],
        ),
        Intent(
            name="search_file",
            patterns=[
                r"(?:search|find|locate|open)\s+(?:for\s+)?(?:the\s+)?(?:file|pdf|document|doc|image|video|spreadsheet|notepad|excel|word|powerpoint|text)\s+(?P<file_name>.+)",
                r"(?:search|find|locate)\s+(?:for\s+)?(?:the\s+)?(?P<file_name>.+)",
            ],
            handler=handle_search_file,
            description="Search for or open a file on the computer",
            examples=["search for invoice pdf", "find the file report.docx", "open the pdf budget spreadsheet"],
            param_names=["file_name"],
        ),
        Intent(
            name="open_project",
            patterns=[
                r"open\s+(?:the\s+)?(?:my\s+)?(?P<project_name>.+?)\s+project",
                r"open\s+(?:the\s+)?(?:my\s+)?project\s+(?P<project_name>.+)",
            ],
            handler=handle_open_project,
            description="Open a software project in VS Code",
            examples=["open my react project", "open the website project"],
            param_names=["project_name"],
        ),
        Intent(
            name="vscode_terminal",
            patterns=[
                r"open\s+(?:the\s+)?terminal",
                r"show\s+(?:the\s+)?terminal",
            ],
            handler=handle_vscode_terminal,
            description="Open the VS Code integrated terminal",
            examples=["open the terminal", "show terminal"],
        ),
        Intent(
            name="create_project",
            patterns=[
                r"create\s+(?:a\s+)?(?:the\s+)?(?:new\s+)?(?P<project_type>\w+)\s+project(?:\s+(?:called|named)\s+(?P<project_name>.+))?",
                r"make\s+(?:a\s+)?(?:the\s+)?(?:new\s+)?(?P<project_type>\w+)\s+project(?:\s+(?:called|named)\s+(?P<project_name>.+))?",
            ],
            handler=handle_create_project,
            description="Create a new software project (like React, Next.js) on the Desktop",
            examples=["create a new react project", "create a next project called my website"],
            param_names=["project_type", "project_name"],
        ),
        Intent(
            name="run_dev_server",
            patterns=[
                r"run\s+(?:the\s+)?(?:dev\s+)?(?:server|project|app)",
                r"start\s+(?:the\s+)?(?:dev\s+)?(?:server|project|app)",
                r"run\s+it",
                r"start\s+it"
            ],
            handler=handle_run_dev_server,
            description="Run the development server for the currently active project",
            examples=["run the dev server", "start the project", "run it"],
        ),
        Intent(
            name="open_dev_server",
            patterns=[
                r"open\s+(?:the\s+)?(?:dev\s+)?(?:server|app|project)\s+(?:in\s+)?(?:the\s+)?browser",
                r"open\s+it\s+(?:in\s+)?(?:the\s+)?browser",
            ],
            handler=handle_open_dev_server,
            description="Open the currently running dev server in the web browser",
            examples=["open it in browser", "open the dev server in the browser"],
        ),
        Intent(
            name="open_app",
            patterns=[
                r"open\s+(?P<app>.+)",
                r"launch\s+(?P<app>.+)",
                r"start\s+(?P<app>.+)",
            ],
            handler=handle_open_app,
            description="Open a desktop application",
            examples=["open notepad", "launch vs code", "start chrome", "open spotify"],
            param_names=["app"],
        ),
        Intent(
            name="close_heavy_apps",
            patterns=[
                r"close\s+(?:all\s+)?heavy\s+(?:applications|apps)",
                r"free\s+(?:up\s+)?(?:some\s+)?(?:memory|ram)",
                r"kill\s+heavy\s+(?:applications|apps)"
            ],
            handler=handle_close_heavy_apps,
            description="Close heavy applications taking up excessive memory",
            examples=["close heavy applications", "free up some memory", "kill heavy apps"],
        ),
        Intent(
            name="close_folder",
            patterns=[
                r"close\s+(?:the\s+)?(?:folder|directory)\s+(?P<path>.+)",
                r"close\s+(?:the\s+)?(?P<path>[\w\s]+?)\s+(?:folder|directory)",
            ],
            handler=handle_close_folder,
            description="Close an open folder window",
            examples=["close the folder friday", "close downloads folder"],
            param_names=["path"],
        ),
        Intent(
            name="close_app",
            patterns=[
                r"close\s+(?P<app>.+)",
                r"quit\s+(?P<app>.+)",
                r"exit\s+(?P<app>.+)",
                r"kill\s+(?P<app>.+)",
            ],
            handler=handle_close_app,
            description="Close a running application",
            examples=["close notepad", "quit chrome", "kill explorer"],
            param_names=["app"],
        ),

        Intent(
            name="create_folder",
            patterns=[
                r"(?:create|make)\s+(?:a\s+|the\s+)?(?:new\s+)?(?:folder|directory)(?:\s+(?:named|name))?\s+(?P<folder_name>.+?)(?:\s+(?:in|on)\s+(?:the\s+)?(?:drive\s+)?(?P<drive>[A-Za-z])(?:\s+drive)?)?$",
            ],
            handler=handle_create_folder,
            description="Create a new folder on the Desktop or a specific drive",
            examples=["create a new folder demo45 on drive E", "make directory test in D drive", "create folder my docs"],
            param_names=["folder_name", "drive"],
        ),
        Intent(
            name="run_command",
            patterns=[
                r"run\s+(?:command\s+)?(?P<cmd>.+)",
                r"execute\s+(?P<cmd>.+)",
                r"terminal\s+(?P<cmd>.+)",
            ],
            handler=handle_run_command,
            description="Run a terminal command",
            examples=["run ipconfig", "execute ping google.com", "run dir"],
            param_names=["cmd"],
        ),
        Intent(
            name="volume_up",
            patterns=[r"(?:volume|turn)\s+up", r"increase\s+volume", r"louder"],
            handler=handle_volume_up,
            description="Increase system volume",
            examples=["volume up", "turn up the volume", "louder"],
        ),
        Intent(
            name="volume_down",
            patterns=[r"(?:volume|turn)\s+down", r"decrease\s+volume", r"quieter"],
            handler=handle_volume_down,
            description="Decrease system volume",
            examples=["volume down", "turn down the volume", "quieter"],
        ),
        Intent(
            name="mute",
            patterns=[r"mute", r"silence", r"shut up"],
            handler=handle_mute,
            description="Mute system audio",
            examples=["mute", "silence", "mute volume"],
        ),
        Intent(
            name="minimize_window",
            patterns=[r"minimize\s+(?:window|this|the window)?$"],
            handler=handle_minimize_window,
            description="Minimize the active window",
            examples=["minimize window", "minimize this"],
        ),
        Intent(
            name="minimize_app",
            patterns=[r"minimize\s+(?:the\s+)?(?P<app>.+)"],
            handler=handle_minimize_app,
            description="Minimize a specific application by name",
            examples=["minimize vscode", "minimize chrome"],
            param_names=["app"],
        ),
        Intent(
            name="maximize_window",
            patterns=[r"maximize\s+(?:window|this|the window)?$"],
            handler=handle_maximize_window,
            description="Maximize the active window",
            examples=["maximize window", "fullscreen"],
        ),
        Intent(
            name="maximize_app",
            patterns=[r"maximize\s+(?:the\s+)?(?P<app>.+)"],
            handler=handle_maximize_app,
            description="Maximize a specific application by name",
            examples=["maximize vscode", "maximize chrome"],
            param_names=["app"],
        ),
        Intent(
            name="close_window",
            patterns=[r"close\s+(?:this\s+)?window", r"close\s+tab"],
            handler=handle_close_window,
            description="Close the active window",
            examples=["close window", "close this window"],
        ),
        Intent(
            name="copy",
            patterns=[r"copy\s+(?:that|this|selection)?", r"ctrl\s*\+?\s*c"],
            handler=handle_clipboard_copy,
            description="Copy selected text to clipboard",
            examples=["copy that", "copy this", "copy"],
        ),
        Intent(
            name="paste",
            patterns=[r"paste\s+(?:that|this|it)?", r"ctrl\s*\+?\s*v"],
            handler=handle_clipboard_paste,
            description="Paste from clipboard",
            examples=["paste", "paste that", "paste it"],
        ),
        Intent(
            name="screenshot",
            patterns=[r"(?:take\s+a?\s*)?screenshot", r"capture\s+screen"],
            handler=handle_screenshot,
            description="Take a screenshot",
            examples=["take a screenshot", "screenshot", "capture screen"],
        ),
        Intent(
            name="sleep",
            patterns=[r"(?:put\s+)?(?:the\s+)?(?:computer|system|pc)\s+(?:to\s+)?sleep", r"sleep\s+(?:mode|now)?"],
            handler=handle_system_sleep,
            description="Put the system to sleep",
            examples=["sleep", "sleep now", "put the computer to sleep"],
        ),
        Intent(
            name="shutdown",
            patterns=[r"shut\s*down\s+(?:the\s+)?(?:computer|system|pc|now)?", r"power\s+off"],
            handler=handle_system_shutdown,
            description="Shut down the system",
            examples=["shutdown", "shut down the computer", "power off"],
        ),
        Intent(
            name="restart",
            patterns=[r"restart\s+(?:the\s+)?(?:computer|system|pc|now)?", r"reboot"],
            handler=handle_system_restart,
            description="Restart the system",
            examples=["restart", "restart the computer", "reboot"],
        ),
        Intent(
            name="set_filename",
            patterns=[
                r"save\s+(?:the\s+)?(?P<app_name>(?!file\b|document\b|changes\b)[\w\s]+?)\s+(?:as|name\s+it|call\s+it)\s+(?P<text>.+)",
                r"(?:save\s+(?:the\s+)?(?:file|document|changes)?\s*)?(?:as|name\s+it|call\s+it)\s+(?P<text>.+)",
                r"(?:name|call)\s+(?:it|the\s+file)\s+(?P<text>.+)",
                r"(?:enter|set|give)\s+(?:the\s+)?(?:file\s+name|name)\s+(?:to\s+)?(?:as\s+)?(?P<text>.+)",
                r"file\s+name\s+(?P<text>.+)",
            ],
            handler=handle_set_filename,
            description="Type a file name and confirm the save",
            examples=["save the file as document1", "name it report", "set the file name to report"],
            param_names=["text", "app_name"],
        ),
        Intent(
            name="type_text",
            patterns=[
                r"type\s+(?:the\s+)?(?:text\s+)?(?P<text>.+)",
                r"write\s+(?P<text>.+)",
            ],
            handler=handle_type_text,
            description="Type specific text using the keyboard",
            examples=["type hello world", "type my email address"],
            param_names=["text", "app_name"],
        ),
        Intent(
            name="lock_screen",
            patterns=[r"lock\s+(?:the\s+)?(?:screen|computer|pc)?", r"lock\s+now"],
            handler=handle_lock_screen,
            description="Lock the screen",
            examples=["lock screen", "lock the computer", "lock now"],
        ),
        Intent(
            name="click_text",
            patterns=[r"(?:click|tap)\s+(?:on\s+)?(?P<text>.+)"],
            handler=handle_click_text,
            description="Click on specific text on the screen using OCR",
            examples=["click on submit", "tap next", "click login"],
            param_names=["text"],
        ),
        Intent(
            name="click",
            patterns=[r"click", r"left\s+click", r"tap"],
            handler=handle_click,
            description="Left click the mouse",
            examples=["click", "left click"],
        ),
        Intent(
            name="double_click",
            patterns=[r"double\s+click"],
            handler=handle_double_click,
            description="Double click the mouse",
            examples=["double click"],
        ),
        Intent(
            name="right_click",
            patterns=[r"right\s+click"],
            handler=handle_right_click,
            description="Right click the mouse",
            examples=["right click"],
        ),
        Intent(
            name="scroll_up",
            patterns=[r"scroll\s+up", r"go\s+up"],
            handler=handle_scroll_up,
            description="Scroll up the screen",
            examples=["scroll up", "go up"],
        ),
        Intent(
            name="scroll_down",
            patterns=[r"scroll\s+down", r"go\s+down"],
            handler=handle_scroll_down,
            description="Scroll down the screen",
            examples=["scroll down", "go down"],
        ),
        Intent(
            name="ask_llm",
            patterns=[
                r"(?:ask\s+(?:ai|jarvis|ace)|tell\s+me)\s+(?P<question>.+)",
                r"(?:what\s+(?:is|are|does|do)|how\s+(?:do|does|can|to))\s+(?P<question>.+)\??",
                r"(?:explain|describe|summarize)\s+(?P<question>.+)",
            ],
            handler=handle_ask_llm,
            description="Ask the AI assistant a question or have a conversation",
            examples=["tell me a joke", "ask ai what is Python", "explain machine learning"],
            param_names=["question"],
        ),
        Intent(
            name="ask_and_type",
            patterns=[
                r"(?:draft|write|compose|generate)\s+(?:and\s+type\s+)?(?P<question>(?:an?\s+)?(?:email|message|letter|report|code|essay|reply|response).+)",
            ],
            handler=handle_ask_and_type,
            description="Ask AI to draft content and physically type it in the active window",
            examples=["draft an email asking for Friday off", "write a professional response"],
            param_names=["question"],
        ),
        Intent(
            name="submit",
            patterns=[
                r"(?:submit|press\s+enter|enter)\s+(?:in\s+)?(?:the\s+)?(?P<app_name>.+)",
                r"submit", r"press\s+enter", r"enter"
            ],
            handler=handle_submit,
            description="Press the Enter key",
            examples=["submit", "press enter", "submit in notepad"],
            param_names=["app_name"],
        ),
        Intent(
            name="dont_save",
            patterns=[
                r"(?:don't|do\s+not)\s+save\s+(?:in\s+)?(?:the\s+)?(?P<app_name>.+)",
                r"don't\s+save", r"do\s+not\s+save"
            ],
            handler=handle_dont_save,
            description="Press 'N' to select Don't Save in dialogs",
            examples=["don't save", "do not save", "don't save in notepad"],
            param_names=["app_name"],
        ),
        Intent(
            name="save_file",
            patterns=[
                r"save\s+(?:the\s+)?(?:file|document|changes)\s+(?:in\s+)?(?:the\s+)?(?P<app_name>.+)",
                r"save\s+(?:the\s+)?(?P<app_name>(?!file|document|changes).+)",
                r"save\s+(?:the\s+)?(?:file|document|changes)?", r"save"
            ],
            handler=handle_save,
            description="Press Ctrl+S or Enter to save",
            examples=["save", "save file", "save the changes", "save the notepad"],
            param_names=["app_name"],
        ),
        Intent(
            name="cancel_dialog",
            patterns=[
                r"(?:cancel|escape|press\s+escape)\s+(?:in\s+)?(?:the\s+)?(?P<app_name>.+)",
                r"cancel", r"escape", r"press\s+escape"
            ],
            handler=handle_cancel,
            description="Press Escape to cancel a dialog",
            examples=["cancel", "escape", "cancel in notepad"],
            param_names=["app_name"],
        ),
    ]

    for intent in intents:
        command_service.register(intent)

    logger.info(f"✅ Registered {len(intents)} built-in command intents")
