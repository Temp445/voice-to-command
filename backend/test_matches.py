import re

elements = [
    {'id': 1, 'text': 'Leads', 'tag': 'a', 'aria': ''},
    {'id': 2, 'text': 'Sales Pipeline Management Guide', 'tag': 'h1', 'aria': ''},
    {'id': 3, 'text': 'Overview', 'tag': 'h2', 'aria': ''},
    {'id': 4, 'text': '> Lead Management\nCreating New Leads\nLead Qualification Process', 'tag': 'div', 'aria': ''},
    {'id': 5, 'text': '> Lead Management', 'tag': 'div', 'aria': ''},
    {'id': 6, 'text': 'Creating New Leads\nLead Qualification Process', 'tag': 'div', 'aria': ''},
    {'id': 7, 'text': 'Creating New Leads', 'tag': 'div', 'aria': ''},
    {'id': 8, 'text': 'Lead Qualification Process', 'tag': 'div', 'aria': ''},
    {'id': 9, 'text': '+ New Lead', 'tag': 'button', 'aria': ''}
]

intent_lower = "expand lead management"
clean_intent = re.sub(r'\b(click|press|hit|open|close|minimize|maximize|expand|collapse|toggle|type|fill|enter|write|put|set|input|select|choose|pick|check|uncheck|tick|upload|attach)\b', '', intent_lower).strip()

exact_matches = []
for el in elements:
    t_val = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', el.get('text', '')).lower().strip()
    a_val = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', el.get('aria', '')).lower().strip()
    if clean_intent == t_val or clean_intent == a_val:
        exact_matches.append(el)

print("Exact matches:", exact_matches)

substr_matches = []
for el in elements:
    text_val = el.get('text', '').lower().strip()
    aria_val = el.get('aria', '').lower().strip()
    if (len(text_val) >= 4 and (text_val in intent_lower or clean_intent in text_val)) or \
       (len(aria_val) >= 4 and (aria_val in intent_lower or clean_intent in aria_val)):
        len_diff = min(
            abs(len(text_val) - len(clean_intent)) if text_val else 999,
            abs(len(aria_val) - len(clean_intent)) if aria_val else 999
        )
        substr_matches.append((len_diff, el))

if substr_matches:
    substr_matches.sort(key=lambda x: x[0])
    best_diff, best_el = substr_matches[0]
    print("Best substring match:", best_el, "with diff:", best_diff)
