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
    context: str = ""   # Surrounding context (e.g. table row text or list item text)
    is_nav_header_or_notification: bool = False


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

            let context = '';
            const row = el.closest('tr');
            if (row) {
                context = (row.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 150);
            } else {
                const li = el.closest('li');
                if (li) {
                    context = (li.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 150);
                }
            }

            const isNavHeaderOrNotification = !!(
                el.closest('header') ||
                el.closest('nav') ||
                el.closest('[role="navigation"]') ||
                el.closest('[role="banner"]') ||
                el.closest('[class*="header" i]') ||
                el.closest('[class*="nav" i]') ||
                el.closest('[class*="notification" i]') ||
                el.closest('[class*="toast" i]') ||
                el.closest('[class*="alert" i]') ||
                el.closest('[class*="popover" i]') ||
                el.closest('[id*="header" i]') ||
                el.closest('[id*="nav" i]') ||
                el.closest('[id*="notification" i]')
            );

            let labelText = '';
            const tagName = el.tagName.toUpperCase();
            if (tagName === 'INPUT' || tagName === 'SELECT' || tagName === 'TEXTAREA' || el.getAttribute('role') === 'combobox') {
                if (el.labels && el.labels.length > 0) {
                    labelText = Array.from(el.labels).map(l => l.innerText || l.textContent || '').join(' ');
                } else if (el.id) {
                    const labelFor = document.querySelector(`label[for="${el.id}"]`);
                    if (labelFor) {
                        labelText = labelFor.innerText || labelFor.textContent || '';
                    }
                }
                if (!labelText.trim()) {
                    const parentLabel = el.closest('label');
                    if (parentLabel) {
                        labelText = parentLabel.innerText || parentLabel.textContent || '';
                    }
                }
                if (!labelText.trim()) {
                    let prev = el.previousElementSibling;
                    while (prev) {
                        const prevText = (prev.innerText || prev.textContent || '').trim();
                        if (prevText && prevText.length < 100) {
                            labelText = prevText;
                            break;
                        }
                        prev = prev.previousElementSibling;
                    }
                }
                if (!labelText.trim()) {
                    const parent = el.parentElement;
                    if (parent) {
                        const parentText = (parent.innerText || parent.textContent || '').trim();
                        if (parentText && parentText.length < 100) {
                            labelText = parentText;
                        }
                    }
                }
            }

            const cleanLabel = labelText.replace(/\s+/g, ' ').trim();
            const displayName = el.getAttribute('aria-label') || el.getAttribute('name') || cleanLabel || '';

            result.push({
                text:                          text,
                role:                          role,
                tag:                           el.tagName.toLowerCase(),
                el_type:                       (el.type || '').toLowerCase(),
                name:                          displayName,
                el_id:                         el.id || '',
                placeholder:                   el.placeholder || '',
                href:                          el.href || '',
                context:                       context,
                is_nav_header_or_notification: isNavHeaderOrNotification
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

        Tab-switch safety: if the cached snapshot belongs to a different URL than
        the current active tab, the cache is force-invalidated before scanning.
        This prevents Layer 0.85 from clicking buttons on the wrong tab.
        """
        # Check cached snapshot against the current active tab URL FIRST.
        # TabRegistry is the authoritative source; fall back to engine if unavailable.
        try:
            from automation.browser.tab_registry import tab_registry as _tr
            _current_page = _tr.get_active()
            _current_url = _current_page.url if _current_page and not _current_page.is_closed() else None
        except Exception:
            _current_url = None

        if self._snapshot and _current_url and self._snapshot.url != _current_url:
            logger.debug(
                f"PageContextService: active tab changed "
                f"({self._snapshot.url!r} → {_current_url!r}) — invalidating snapshot"
            )
            self._snapshot = None

        cached = self.get_cached_snapshot()
        if cached:
            return cached

        try:
            from automation.browser.browser_engine import BrowserEngine, _run_in_playwright
            engine = BrowserEngine()
            if engine._context is None:
                return None

            async def _scan():
                # Prefer TabRegistry for page resolution (avoids the heuristic pipeline)
                try:
                    from automation.browser.tab_registry import tab_registry as _tr2
                    page = _tr2.get_active()
                    if page and page.is_closed():
                        page = None
                except Exception:
                    page = None
                if not page:
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
                            context=e.get("context", ""),
                            is_nav_header_or_notification=e.get("is_nav_header_or_notification", False),
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
    Takes into account action verb matching, context overlap, and header/nav/notification penalties.
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

        # Check if element is in header, nav, or notification
        in_header_nav_notification = getattr(el, "is_nav_header_or_notification", False)
        query_mentions_nav_or_notification = any(
            w in q for w in ["notification", "bell", "profile", "header", "navbar", "navigation", "nav", "menu", "sidebar", "toast", "alert"]
        )

        # Extract action verb if present
        action_verb = None
        q_target = q

        action_patterns = [
            ("navigate to", "navigate to"),
            ("go to", "go to"),
            ("click on", "click on"),
            ("click", "click"),
            ("tap on", "tap on"),
            ("tap", "tap"),
            ("press", "press"),
            ("hit", "hit"),
            ("view", "view"),
            ("show", "show"),
            ("inspect", "inspect"),
            ("edit", "edit"),
            ("update", "update"),
            ("delete", "delete"),
            ("remove", "remove"),
            ("open", "open"),
            ("select", "select"),
        ]

        for pat_str, verb in action_patterns:
            if q.startswith(pat_str + " "):
                action_verb = verb
                q_target = q[len(pat_str) + 1:].strip()
                break

        filler_words = {"the", "a", "an", "on", "to", "at", "for", "with", "request", "employee", "button", "link", "record", "item"}
        q_target_words = [w for w in q_target.split() if w not in filler_words]
        q_target_clean = " ".join(q_target_words)

        score = 0

        # Check if label is a generic action verb
        is_action_label = label == action_verb or (action_verb and (label.startswith(action_verb + " ") or label.endswith(" " + action_verb)))
        if action_verb and (label == action_verb or label in action_verb or action_verb in label):
            is_action_label = True

        if is_action_label and q_target_words:
            # Check context overlap
            context = getattr(el, "context", "").lower()
            if context:
                context_words = set(context.split())
                overlap = len(set(q_target_words) & context_words)
                if overlap > 0:
                    score = 80 + int((overlap / len(q_target_words)) * 20)
                else:
                    score = 10
            else:
                score = 20
        else:
            if label == q or (q_target_clean and label == q_target_clean):
                score = 100
            elif q_target_clean and (q_target_clean in label or label in q_target_clean):
                score = 90
            elif q in label or label in q:
                score = 85
            elif label.startswith(q) or (q_target_clean and label.startswith(q_target_clean)):
                score = 75
            else:
                label_words = set(label.split())
                query_words = set(q_target_clean.split()) if q_target_clean else q_words
                overlap = len(query_words & label_words)
                if overlap > 0:
                    score = int((overlap / max(len(query_words), len(label_words))) * 60)

        # Apply penalty for header/nav/notification elements if the query is not targeting them
        if in_header_nav_notification and not query_mentions_nav_or_notification:
            score -= 60

        if score > best_score:
            best_score = score
            best_el = el

    if best_score >= min_score:
        logger.debug(f"Snapshot match: '{query}' → '{best_el.text}' (score={best_score})")
        return best_el
    return None


# ── Singleton ─────────────────────────────────────────────────────────────────
page_context_service = PageContextService()
