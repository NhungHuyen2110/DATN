"""High-confidence coverage check; unconsumed meaning always goes to planner."""
import re
from .dialogue_plan import DialoguePlan, Operation
from .dialogue_state_extractor import extract_state_changes, MATERIALS
from .entity_linking import link_query, normalize, load_entities
from .shopping_advice import budget_text, _MONEY


def fast_plan(message, state, parse_price, pending=None):
    """Accept a completely covered positive slot request, never a partial parse.

    Entity/quantity/money grammars are primitives. No failed audit utterance is
    used as a special case. Negation, references and unknown content defer.
    """
    text=normalize(message)
    if re.search(r'\b(?:khong|chang|dung|bo|go|xoa|thay|doi|hon|sao|vi|gi|nao|hay|hoac)\b',text):
        return None
    understanding=link_query(message)
    if understanding['needs_clarification']:
        return None
    try:
        updates,clear=extract_state_changes(message,parse_price)
    except (ValueError,TypeError):
        return None
    if clear or not updates or not state and 'category' not in updates:
        return None
    if any(k in updates for k in ('audience','style','price_preference')):
        return None  # Advice/preference semantics require full-context planning.
    remaining=text
    for entity in load_entities()['entities']:
        for alias in sorted(entity['aliases'],key=len,reverse=True):
            remaining=re.sub(r'(?<!\w)'+re.escape(normalize(alias))+r'(?!\w)',' ',remaining)
    for alias in sorted(MATERIALS,key=len,reverse=True):
        remaining=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',' ',remaining)
    if updates.get('min_price') is not None or updates.get('max_price') is not None:
        # Match original punctuation/units, then remove only spans recognized as
        # money. Unknown budget qualifiers remain and prevent fast acceptance.
        for match in _MONEY.finditer(budget_text(message)):
            remaining=remaining.replace(normalize(match.group()),' ')
    if 'top_k' in updates:
        remaining=re.sub(r'\b(?:top\s*)?(?:\d{1,2}|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\s*(?:mau|mon|san pham|ket qua)?\b',' ',remaining)
    fillers={'tim','xem','cho','toi','minh','em','ban','giup','voi','nhe','nha','a','goi','y',
             'muon','can','san','pham','mau','mon','truoc','tham','khao','lay','hien','thi'}
    if set(remaining.split())-fillers:
        return None
    operations=[]
    for field,value in updates.items():
        if field in ('min_exclusive','max_exclusive'):
            continue
        operations.append(Operation(field=field,op='SET',value=str(value),evidence=message,
                          exclusive=updates.get(field.replace('_price','_exclusive'),False)
                          if field in {'min_price','max_price'} else False))
    return DialoguePlan(intent='refine_search' if state else 'new_search',operations=operations)
