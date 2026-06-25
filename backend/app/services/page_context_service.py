"""
ACE Voice Controller — Page Context Service

Scans the active browser page and caches a structured snapshot of all visible,
interactive DOM elements. This snapshot is used by:

  - Layer 0.85 in command_service.py  → fast text-match click without Playwright round-trip
  - LLM fallback (llm_service.py)     → page-aware intent classification
  - Vision fallback (vision_service.py) → grounding for coordinate-based clicks

Caching strategy:
  - TTL: 3 seconds (configurable via PAGE_CONTEXT_TTL_SECONDS)
  - Invalidated immediately when page URL changes
  - Thread-safe: all Playwright work runs on _playwright_loop via _run_in_playwright
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


PAGE_CONTEXT_TTL_SECONDS = 3.0  # Cache duration before a fresh scan is triggered


@dataclass
class PageElement:
    """Represents a single visible, interactive DOM element."""
    text: str           # Visible label / innerText (stripped)
    role: str           # button | link | input | select | tab | menuitem | other
    tag: str            # a | button | input | select | textarea
    el_type: str        # text | password | email | submit | checkbox | etc.
    name: str           # aria-label or name attribute
    el_id: str          # element id attribute
    placeholder: str    # input placeholder text
    href: str           # href for links


@dataclass
class PageSnapshot:
    """A point-in-time snapshot of the active browser page's interactive elements."""
    url: str
    title: str
    elements: list[PageElement]
    captured_at: float = field(default_factory=time.time)

    def age(self) -> float:
        return time.time() - self.captured_at

    def is_stale(self) -> bool:
        return self.age() > PAGE_CONTEXT_TTL_SECONDS

    def clickable(self) -> list[PageElement]:
        """Return only elements that can be clicked (buttons and links)."""
        return [e for e in self.elements if e.role in ("button", "link", "tab", "menuitem")]

    def inputs(self) -> list[PageElement]:
        """Return only input/select/textarea elements."""
        return [e for e in self.elements if e.tag in ("input", "select", "textarea")]

    def summary_for_llm(self, max_elements: int = 25) -> str:
        """
        Returns a compact, LLM-friendly summary of the page elements.
        Prioritizes buttons and links first, then inputs.
        """
        lines = [f"Page: {self.title} ({self.url})"]

        clickables = self.clickable()[:max_elements]
        if clickables:
            labels = [e.text or e.name or e.el_id for e in clickables if e.text or e.name]
            lines.append(f"Buttons/Links: {labels}")

        inputs_ = self.inputs()[:10]
        if inputs_:
            inp_descs = []
            for e in inputs_:
                desc = e.el_type or e.tag
                label = e.placeholder or e.name or e.el_id or e.text
                if label:
                    desc += f":{label}"
                inp_descs.append(desc)
            lines.append(f"Input fields: {inp_descs}")

        return "\n".join(lines)


# ── DOM Extraction JS ─────────────────────────────────────────────────────────

_EXTRACT_JS = """
() => {
    const selector = [
        'a[href]', 'button', 'input', 'select', 'textarea',
        "[role='button']", "[role='link']", "[role='tab']",
        "[role='menuitem']", "[role='option']", "[role='checkbox']",
        "[role='radio']", "[role='switch']", "[role='combobox']"
    ].join(', ');

    const elements = Array.from(document.querySelectorAll(selector));
    const result = [];

    for (const el of elements) {
        try {
            const style = window.getComputedStyle(el);
            // Skip hidden elements
            if (style.display === 'none' || style.visibility === 'hidden' ||
                el.offsetWidth === 0 || el.offsetHeight === 0) continue;
            // Skip elements scrolled far out of view (> 3 viewports away)
            const rect = el.getBoundingClientRect();
            if (rect.bottom < -window.innerHeight * 3 ||
                rect.top > window.innerHeight * 4) continue;

            const text = (el.innerText || el.textContent || '').trim().slice(0, 120);
            const role = el.getAttribute('role') ||
                         (el.tagName === 'A' ? 'link' :
                          el.tagName === 'BUTTON' ? 'button' :
                          el.tagName === 'INPUT' ? 'input' :
                          el.tagName === 'SELECT' ? 'select' :
                          el.tagName === 'TEXTAREA' ? 'input' : 'other');

            result.push({
                text:        text,
                role:        role,
                tag:         el.tagName.toLowerCase(),
                el_type:     (el.type || '').toLowerCase(),
                name:        el.getAttribute('aria-label') || el.getAttribute('name') || '',
                el_id:       el.id || '',
                placeholder: el.placeholder || '',
                href:        el.href || ''
            });

            if (result.length >= 150) break;  // Safety cap
        } catch (e) { /* skip malformed elements */ }
    }
    return result;
}
"""


# ── Service ───────────────────────────────────────────────────────────────────

class PageContextService:
    """
    Singleton service that maintains a short-lived snapshot of the active
    browser page's interactive elements.
    """

    def __init__(self):
        self._snapshot: Optional[PageSnapshot] = None

    def invalidate(self) -> None:
        """Force the next call to get_snapshot() to do a fresh scan."""
        self._snapshot = None
        logger.debug("Page context snapshot invalidated.")

    def get_cached_snapshot(self) -> Optional[PageSnapshot]:
        """
        Return the cached snapshot if it exists and is not stale.
        Does NOT trigger a new scan — safe to call from sync context.
        """
        if self._snapshot and not self._snapshot.is_stale():
            return self._snapshot
        return None

    async def get_snapshot(self) -> Optional[PageSnapshot]:
        """
        Return a fresh (or cached) snapshot of the active browser page.
        Performs a Playwright DOM scan if the cache is stale or missing.
        All Playwright work is dispatched to _playwright_loop via _run_in_playwright.
        """
        cached = self.get_cached_snapshot()
        if cached:
            return cached

        try:
            from automation.browser.browser_engine import BrowserEngine, _run_in_playwright
            engine = BrowserEngine()
            if engine._context is None:
                return None

            async def _scan():
                page = await engine.get_active_page()
                if not page:
                    return None
                try:
                    url = page.url
                    title = await page.title()
                    raw = await page.evaluate(_EXTRACT_JS)
                    elements = [
                        PageElement(
                            text=e.get("text", ""),
                            role=e.get("role", "other"),
                            tag=e.get("tag", ""),
                            el_type=e.get("el_type", ""),
                            name=e.get("name", ""),
                            el_id=e.get("el_id", ""),
                            placeholder=e.get("placeholder", ""),
                            href=e.get("href", ""),
                        )
                        for e in (raw or [])
                    ]
                    return PageSnapshot(url=url, title=title, elements=elements)
                except Exception as e:
                    logger.debug(f"Page context DOM scan failed: {e}")
                    return None

            snapshot = await _run_in_playwright(_scan())
            if snapshot:
                self._snapshot = snapshot
                logger.debug(
                    f"Page context snapshot: {len(snapshot.elements)} elements "
                    f"on '{snapshot.title}'"
                )
            return snapshot

        except Exception as e:
            logger.debug(f"PageContextService.get_snapshot() error: {e}")
            return None


# ── Matching Helper ───────────────────────────────────────────────────────────

def find_best_element(
    elements: list[PageElement],
    query: str,
    min_score: int = 40,
    roles: tuple[str, ...] = ("button", "link", "tab", "menuitem"),
) -> Optional[PageElement]:
    """
    Score each element against the voice query and return the best match.

    Scoring:
      100 — exact text match (case-insensitive)
       90 — query is a substring of element text
       70 — element text starts with query
       variable — word-overlap ratio × 60 (min score = min_score to qualify)

    Only considers elements whose role is in `roles` (default: clickable elements).
    """
    q = query.lower().strip()
    q_words = set(q.split())

    best_el: Optional[PageElement] = None
    best_score = 0

    for el in elements:
        if roles and el.role not in roles:
            continue

        # Build candidate label: prefer visible text, fall back to name/placeholder/id
        label = (el.text or el.name or el.placeholder or el.el_id).lower().strip()
        if not label:
            continue

        # Scoring
        if label == q:
            score = 100
        elif q in label or label in q:
            score = 90
        elif label.startswith(q):
            score = 70
        else:
            label_words = set(label.split())
            overlap = len(q_words & label_words)
            if overlap == 0:
                continue
            score = int((overlap / max(len(q_words), len(label_words))) * 60)

        if score > best_score:
            best_score = score
            best_el = el

    if best_score >= min_score:
        logger.debug(f"Snapshot match: '{query}' → '{best_el.text}' (score={best_score})")
        return best_el
    return None


# ── Singleton ─────────────────────────────────────────────────────────────────
page_context_service = PageContextService()
