"""
Smoke tests for the TabRegistry multi-tab architecture.

Run from backend/ with:
    pytest tests/test_tab_registry.py -v

These tests use MagicMock pages — no real browser needed.
"""

import asyncio
import time
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_page(url: str = "https://example.com", closed: bool = False) -> MagicMock:
    """Create a mock Playwright Page."""
    page = MagicMock()
    page.url = url
    page.is_closed.return_value = closed
    page.on = MagicMock()  # lifecycle hooks
    return page


def _fresh_registry():
    """Return a brand-new TabRegistry instance (bypasses singleton for testing)."""
    from automation.browser.tab_registry import TabRegistry
    reg = object.__new__(TabRegistry)
    reg._init()
    return reg


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestTabRegistration:
    def test_register_assigns_stable_uuid(self):
        reg = _fresh_registry()
        page = _make_page("https://youtube.com")
        tab_id = reg.register(page)

        assert isinstance(tab_id, str)
        assert len(tab_id) == 36  # UUID4 format
        assert reg.get_tab_id(page) == tab_id

    def test_register_is_idempotent(self):
        reg = _fresh_registry()
        page = _make_page()
        id1 = reg.register(page)
        id2 = reg.register(page)
        assert id1 == id2

    def test_register_multiple_pages_get_different_ids(self):
        reg = _fresh_registry()
        p1 = _make_page("https://youtube.com")
        p2 = _make_page("https://github.com")
        p3 = _make_page("https://chatgpt.com")

        id1 = reg.register(p1)
        id2 = reg.register(p2)
        id3 = reg.register(p3)

        assert len({id1, id2, id3}) == 3  # all unique

    def test_unregister_removes_page(self):
        reg = _fresh_registry()
        page = _make_page()
        reg.register(page)
        reg.unregister(page)

        assert reg.get_tab_id(page) is None

    def test_unregister_nonexistent_page_is_safe(self):
        reg = _fresh_registry()
        page = _make_page()
        reg.unregister(page)  # should not raise


class TestActiveTabTracking:
    def test_set_and_get_active(self):
        reg = _fresh_registry()
        p1 = _make_page("https://youtube.com")
        p2 = _make_page("https://chatgpt.com")
        reg.register(p1)
        reg.register(p2)

        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            reg.set_active(p2)

        result = reg.get_active()
        assert result is p2

    def test_active_tab_youtube_then_chatgpt_returns_chatgpt(self):
        """Core regression: command must go to ChatGPT, not YouTube."""
        reg = _fresh_registry()
        youtube = _make_page("https://youtube.com")
        github  = _make_page("https://github.com")
        chatgpt = _make_page("https://chatgpt.com")

        reg.register(youtube)
        reg.register(github)
        reg.register(chatgpt)

        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            reg.set_active(youtube)  # simulates first ACE navigation
            reg.set_active(chatgpt)  # simulates user clicking ChatGPT tab

        assert reg.get_active() is chatgpt, (
            "Expected ChatGPT to be active, but got a different tab. "
            "This is the core multi-tab routing bug."
        )

    def test_set_active_auto_registers_unknown_page(self):
        reg = _fresh_registry()
        page = _make_page()

        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            reg.set_active(page)  # page not yet registered

        assert reg.get_tab_id(page) is not None


class TestClosedPageSafety:
    def test_get_active_returns_none_for_closed_page(self):
        reg = _fresh_registry()
        page = _make_page()
        reg.register(page)
        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            reg.set_active(page)

        # Simulate page closing
        page.is_closed.return_value = True

        result = reg.get_active()
        assert result is None

    def test_closed_active_tab_falls_back_to_next_live_tab(self):
        reg = _fresh_registry()
        p1 = _make_page("https://youtube.com")
        p2 = _make_page("https://chatgpt.com")
        reg.register(p1)
        reg.register(p2)

        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            reg.set_active(p1)

        # p1 closes
        p1.is_closed.return_value = True
        reg.unregister(p1)

        # Registry should now return p2 as active
        result = reg.get_active()
        assert result is p2

    def test_server_crash_does_not_raise(self):
        reg = _fresh_registry()
        page = _make_page()
        reg.register(page)

        # Simulate a crash handler call
        reg._on_page_crashed(page)
        assert reg.get_tab_id(page) is None  # cleaned up


class TestAllTabs:
    def test_all_tabs_returns_correct_count(self):
        reg = _fresh_registry()
        pages = [_make_page(f"https://site{i}.com") for i in range(3)]
        for p in pages:
            reg.register(p)

        tabs = reg.all_tabs()
        assert len(tabs) == 3

    def test_all_tabs_marks_active_correctly(self):
        reg = _fresh_registry()
        p1 = _make_page("https://youtube.com")
        p2 = _make_page("https://chatgpt.com")
        reg.register(p1)
        reg.register(p2)

        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            reg.set_active(p2)

        tabs = reg.all_tabs()
        active_tabs = [t for t in tabs if t.is_active]
        assert len(active_tabs) == 1
        assert active_tabs[0].url == "https://chatgpt.com"

    def test_all_tabs_excludes_closed_pages(self):
        reg = _fresh_registry()
        p1 = _make_page("https://youtube.com")
        p2 = _make_page("https://chatgpt.com", closed=True)
        reg.register(p1)
        reg.register(p2)

        tabs = reg.all_tabs()
        urls = [t.url for t in tabs]
        assert "https://youtube.com" in urls
        assert "https://chatgpt.com" not in urls


class TestDiskRecovery:
    def test_recover_from_disk_exact_url_match(self):
        reg = _fresh_registry()
        reg._persisted = {
            "active_tab_id": str(uuid.uuid4()),
            "active_url": "https://chatgpt.com",
        }

        pages = [
            _make_page("https://youtube.com"),
            _make_page("https://chatgpt.com"),
        ]
        for p in pages:
            reg.register(p)

        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            recovered = reg.recover_from_disk(pages)

        assert recovered is not None
        assert recovered.url == "https://chatgpt.com"

    def test_recover_from_disk_no_match_returns_none(self):
        reg = _fresh_registry()
        reg._persisted = {
            "active_url": "https://closed-tab.com"
        }
        pages = [_make_page("https://youtube.com")]
        for p in pages:
            reg.register(p)

        with patch.object(reg, "_broadcast_tab_changed"), \
             patch.object(reg, "_persist"):
            result = reg.recover_from_disk(pages)

        assert result is None

    def test_recover_from_disk_no_saved_state_returns_none(self):
        reg = _fresh_registry()
        reg._persisted = {}
        result = reg.recover_from_disk([_make_page()])
        assert result is None
