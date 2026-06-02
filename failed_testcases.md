# ACE Voice Controller - Failed Test Scenarios

The following test scenarios currently fail based on the system's current architecture and available intents.

| ID | Category | Command | Reason for Failure |
|---|---|---|---|
| 14 | Context Awareness | Create a Python file | No dedicated built-in intent for complex UI manipulation without exact keystroke context. |
| 15 | Context Awareness | Name it test.py | Pronoun resolution ("it") across separate commands relies heavily on the LLM's short-term memory which is inconsistent for precision GUI actions. |
| 28-37 | Browser Automation | Web interactions (YouTube, Gmail, Play video, Scroll) | The Playwright browser automation module is not fully integrated into the voice pipeline for real-time DOM manipulation (like clicking "the first video"). |
| 44 | File Management | Show recent files | Windows recent files API is restricted; no built-in intent exists for fetching this yet. |
| 59-63 | OCR & Vision | Screen reading, image extraction | Vision capabilities and screen capturing (OCR) are **not currently implemented** in the codebase. The LLM cannot "see" your screen. |
| 93 | Advanced Assistant | Find all PDF files on my computer | Indexer only scans specific user directories to save memory. A full `C:\` drive search would timeout. |
| 94 | Advanced Assistant | Open the latest downloaded file | Missing a specific function to sort the `Downloads` directory by date via voice command. |
| TEST_2 | Web Search | Search YouTube for LoFi music. | No dedicated YouTube search intent; falls back to a generic Google search. |
| TEST_2 | Context Continuation | Open the first result. | No real-time DOM manipulation (Playwright) intents mapped for voice navigation yet. |
| TEST_2 | File Management | Open my Python project. | Ambiguous path; system does not have a 'default project' registry yet. |
| TEST_2 | VS Code | Open the terminal. | No built-in intent for VS Code specific shortcuts (Ctrl+`). |
| TEST_2 | Browser Usage | Play first video / Pause / Go back / New tab | Specific browser DOM manipulation (clicking, pausing video players) via voice is missing because Playwright scripts are not exposed to the LLM router yet. |
| TEST_2 | Human-Like Requests | Find the document I was working on yesterday. | Windows recent files API is restricted; system lacks a robust temporal file indexer. |
| TEST_2 | Human-Like Requests | Close everything except VS Code. | Dangerous global operation; no built-in intent allows killing all processes safely. |
| TEST_2 | Human-Like Requests | Open my work applications / Start my dev env. | System does not support named application groups/macros yet. |
