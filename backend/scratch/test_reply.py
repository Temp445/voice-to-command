import re

_ACTION_VERB_RE = re.compile(
    r'^(?:click(?:ed)?|tap(?:ped)?|open(?:ed)?|go\s+to|navigate\s+to|toggle(?:d)?|'
    r'show(?:n)?|press(?:ed)?|launch(?:ed)?|expand(?:ed)?|hit|select(?:ed)?)\s+(?:the\s+|on\s+)?',
    re.IGNORECASE
)
_NAV_WORDS = {'page', 'section', 'dashboard', 'home', 'screen', 'view', 'route'}
_UI_TOGGLE_WORDS = {'sidebar', 'menu', 'drawer', 'navbar', 'toolbar', 'hamburger', 'navigation', 'nav'}

def _friendly_click_reply(raw_text):
    label = _ACTION_VERB_RE.sub('', raw_text).strip()
    label_lower = label.lower()
    if any(w in label_lower for w in _UI_TOGGLE_WORDS):
        display = label_lower.replace('the ', '').strip()
        return f'Opened the {display}.'
    if any(w in label_lower for w in _NAV_WORDS):
        title = label.title().replace(' Page', '').replace(' Section', '')
        return f'Got it, heading to {title}.'
    if len(label.split()) <= 2:
        return 'Done!'
    return f'Done — selected "{label}".'

tests = [
    'open the sidebar',
    'open sidebar',
    'click the menu',
    'toggle navigation',
    'go to dashboard',
    'advance request',
    'advance request page',
    'submit',
    'Sign In',
    'click the get started button',
    'open advance request',
]
for t in tests:
    print(f'{t!r:45} -> {_friendly_click_reply(t)}')
