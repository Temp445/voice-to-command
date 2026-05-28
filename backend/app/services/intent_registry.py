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
    ctrl = AppController()
    return await ctrl.close_application(app.strip())


async def handle_search_google(query: str = "", **_) -> str:
    from automation.browser.search import BrowserSearch
    return await BrowserSearch().google(query.strip())


async def handle_search_youtube(query: str = "", **_) -> str:
    from automation.browser.search import BrowserSearch
    return await BrowserSearch().youtube(query.strip())


async def handle_open_website(url: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    bc = BrowserController()
    url = url.strip()
    # Append .com if it's just a raw name without domain or protocol
    if "." not in url and not url.startswith("http"):
        url = url + ".com"
    await bc.navigate(url)
    return f"Opened {url}"


async def handle_open_folder(path: str = "", **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().open_folder(path.strip())


async def handle_create_folder(folder_name: str = "", **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().create_folder(folder_name.strip())


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


async def handle_type_text(text: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().type_text(text.strip())
    return f"Typed: {text}"


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


async def handle_submit(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().press_enter()
    return "Submitted"


# ─── Register All Intents ────────────────────────────────────────────────────

def register_all_intents() -> None:
    """Call this once at startup to wire up all built-in command intents."""

    intents = [
        Intent(
            name="search_youtube",
            patterns=[
                r"(?:search|find|play)\s+(?P<query>.+)\s+on youtube",
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
                r"(?:search|google)\s+(?:for\s+)?(?P<query>.+)",
                r"(?:look up|find)\s+(?P<query>.+)\s+on google",
            ],
            handler=handle_search_google,
            description="Search Google in the browser",
            examples=["search for python tutorials", "google the weather", "search machine learning"],
            param_names=["query"],
        ),
        Intent(
            name="open_website",
            patterns=[
                r"(?:open|go to|visit|navigate to)\s+(?P<url>(?:https?://)?[\w\-\.]+\.\w{2,}(?:/\S*)?)",
                r"(?:open|go to|visit)\s+(?P<url>youtube|google|github|netflix|spotify|twitter|facebook|gmail|amazon|reddit)"
            ],
            handler=handle_open_website,
            description="Open a website URL in the browser",
            examples=["open github.com", "go to youtube.com", "visit google.com"],
            param_names=["url"],
        ),
        Intent(
            name="open_folder",
            patterns=[
                r"open\s+(?:folder|directory)\s+(?P<path>.+)",
                r"show\s+(?:me\s+)?(?P<path>.+)\s+(?:folder|directory)",
            ],
            handler=handle_open_folder,
            description="Open a folder in Windows Explorer",
            examples=["open folder downloads", "open folder C:/Users", "show me documents folder"],
            param_names=["path"],
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
                r"(?:create|make)\s+(?:a\s+)?(?:new\s+)?(?:folder|directory)\s+(?P<folder_name>.+)",
            ],
            handler=handle_create_folder,
            description="Create a new folder on the Desktop",
            examples=["create folder demo44", "make a directory test", "create a new folder my_docs"],
            param_names=["folder_name"],
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
            patterns=[r"minimize\s+(?:window|this|the window)?", r"hide\s+window"],
            handler=handle_minimize_window,
            description="Minimize the active window",
            examples=["minimize window", "minimize this"],
        ),
        Intent(
            name="maximize_window",
            patterns=[r"maximize\s+(?:window|this|the window)?", r"fullscreen"],
            handler=handle_maximize_window,
            description="Maximize the active window",
            examples=["maximize window", "fullscreen"],
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
            name="type_text",
            patterns=[r"type\s+(?P<text>.+)", r"write\s+(?P<text>.+)"],
            handler=handle_type_text,
            description="Type text using the keyboard",
            examples=["type hello world", "write my name", "type this sentence"],
            param_names=["text"],
        ),
        Intent(
            name="lock_screen",
            patterns=[r"lock\s+(?:the\s+)?(?:screen|computer|pc)?", r"lock\s+now"],
            handler=handle_lock_screen,
            description="Lock the screen",
            examples=["lock screen", "lock the computer", "lock now"],
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
            name="submit",
            patterns=[r"submit", r"press\s+enter", r"enter"],
            handler=handle_submit,
            description="Press the Enter key",
            examples=["submit", "press enter", "enter"],
        ),
    ]

    for intent in intents:
        command_service.register(intent)

    logger.info(f"✅ Registered {len(intents)} built-in command intents")
