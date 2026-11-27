"""Validate quoted, typed operations atomically before applying shopping state."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from .dialogue_plan import DialoguePlan, allowed_entities
from .dialogue_state import ShoppingState, StatePatch
from .entity_linking import normalize, link_query
from .semantic_intent_validator import evidence_matches


class InvalidDialoguePlan(ValueError):
    """No operation in an invalid proposal may be applied."""


@dataclass(frozen=True)
class ValidatedDialoguePlan:
    intent: str
    state: ShoppingState
    operations: tuple
    references: tuple = ()
    pending_slot: str | None = None
    query: str | None = None


def _amount_grounded(value, evidence):
    """Check numeric conversion against the quote, independent of LLM prices."""
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        return False
    # Monetary units/conversions are lexical primitives, not sentence templates.
    folded = evidence.casefold().replace(',', '.')
    numbers = re.findall(r'(?<!\w)\d+(?:\.\d+)?', folded)
    units = normalize(evidence).split()
    if not (set(units) & {'trieu','tr','nghin','ngan','k','dong','vnd'}
            or any(term in normalize(evidence) for term in ('gia','ngan sach','tien','chi tieu'))):
        return False
    multiplier = Decimal(1000000) if any(t in units for t in ('trieu', 'tr')) else Decimal(1000) if any(t in units for t in ('nghin', 'ngan', 'k')) else Decimal(1)
    return any(Decimal(n) * multiplier == amount for n in numbers)


def _count_grounded(value, evidence):
    words = {'mot':1,'hai':2,'ba':3,'bon':4,'nam':5,'sau':6,'bay':7,'tam':8,'chin':9,'muoi':10}
    return str(value) in normalize(evidence).split() or any(words.get(t)==int(value) for t in normalize(evidence).split())


def _entity_grounded(field, value, evidence, encoder=None):
    allowed = allowed_entities()[field]
    if value not in allowed:
        return False
    if field == 'material':
        from .dialogue_state_extractor import MATERIALS
        return any(canonical == value and ' '+alias+' ' in ' '+normalize(evidence)+' '
                   for alias,canonical in MATERIALS.items())
    return any(e['canonical_id']==value and e['label'].lower()==field
               for e in link_query(evidence, encoder=encoder)['entities'])


def _positive_entity(field,value,message):
    aliases=[]
    if field=='material':
        from .dialogue_state_extractor import MATERIALS
        aliases=[a for a,v in MATERIALS.items() if v==value]
    else:
        from .entity_linking import load_entities
        aliases=[normalize(a) for e in load_entities()['entities']
                 if e['label'].lower()==field and e['canonical_id']==value for a in e['aliases']]
    found=False
    for clause in re.split(r'[,;.!?]',message):
        text=normalize(clause)
        for alias in aliases:
            for match in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text):
                found=True
                prefix=re.split(r'\b(?:nhung|ma|sang|qua)\b',text[:match.start()])[-1]
                if not re.search(r'\b(?:khong|chang|dung|bo|go|xoa)\b',prefix):
                    return True
    # Semantically linked paraphrases are still accepted only through the
    # entity linker threshold, while explicit negative mentions are rejected.
    return not found and not re.search(r'\b(?:khong|chang|dung|bo|go|xoa)\b',normalize(message))


def _complete_coverage(plan,message):
    """Reject missing semantic dimensions even after a partial lexical match."""
    fields={op.field for op in plan.operations}
    if plan.intent not in {'new_search','refine_search','consultation','clarification'}:
        return
    entities=link_query(message)['entities']
    for entity in entities:
        if entity['label'].lower() not in fields:
            raise InvalidDialoguePlan('Unaccounted explicit entity dimension')
    from .dialogue_state_extractor import MATERIALS
    text=normalize(message)
    if any(' '+a+' ' in ' '+text+' ' for a in MATERIALS) and 'material' not in fields:
        raise InvalidDialoguePlan('Unaccounted material dimension')
    if re.search(r'\d+(?:[.,]\d+)?\s*(?:triệu|trieu|tr\b|nghìn|nghin|ngàn|ngan|đồng|dong|vnd)\b',message,re.I):
        if not fields & {'min_price','max_price'}:
            raise InvalidDialoguePlan('Unaccounted monetary dimension')
    from .dialogue_state_extractor import extract_state_changes
    from .retrieval import extract_price_filter
    known,_=extract_state_changes(message,extract_price_filter)
    for field in ('min_price','max_price'):
        if known.get(field) is not None and field not in fields:
            raise InvalidDialoguePlan('Unaccounted explicit price boundary')
    if re.search(r'\b(?:\d+|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\s+(?:mau|mon|san pham|ket qua|chiec|cai|doi)\b',text):
        # Ordinal/card discussion is handled by a non-shopping intent instead.
        if not fields & {'top_k','references'}:
            raise InvalidDialoguePlan('Unaccounted result-count dimension')


def _destructive_scope(field, evidence, previous):
    """Independent safety vocabulary for destructive speech acts, not NLU routing.

    Unrecognized paraphrases abstain instead of weakening hard constraints.
    This is intentionally conservative and is measured in acceptance testing.
    """
    text=normalize(evidence)
    action=any(' '+term+' ' in ' '+text+' ' for term in
               ('bo','go','xoa','khong can','khong gioi han','khong bat buoc','nao cung duoc'))
    if not action:
        return False
    scopes={'material':('chat lieu',),'gemstone':('da',),
            'min_price':('san','toi thieu','thap nhat','min'),
            'max_price':('tran','toi da','cao nhat','max'),
            'price_preference':('uu tien','sap','xep','thich'),
            'category':('loai','danh muc'),'audience':('doi tuong',),'style':('phong cach',)}
    terms=list(scopes.get(field,()))
    if field in ('min_price','max_price'):
        # Broad budget removal may clear both bounds. A named floor/ceiling may
        # not be used as evidence to erase the opposite bound.
        opposite=scopes['max_price' if field=='min_price' else 'min_price']
        if any(term in text for term in opposite) and not any(term in text for term in terms):
            return False
        terms+=['ngan sach','gioi han gia','gioi han tien']
    value=getattr(previous,field,None)
    if field in allowed_entities() and value in allowed_entities()[field]:
        terms.append(normalize(allowed_entities()[field][value]))
    return any(' '+term+' ' in ' '+text+' ' for term in terms)


def validate_dialogue_plan(plan, message, previous=None, *, products=(), pending=None,
                           encoder=None, verified_attributes=(), top_k=3):
    """All changes need current-message evidence. Product prices come from cards.

    Quote/type/entity checks do not prove arbitrary semantic entailment. Ambiguous
    or contradictory proposals abstain; this validator grants no business access.
    """
    if not isinstance(plan, DialoguePlan):
        raise InvalidDialoguePlan('Schema validation required')
    _complete_coverage(plan,message)
    before = previous or ShoppingState(top_k=top_k)
    updates, clear, seen, references = {}, set(), set(), ()
    pending_slot = None
    reset = False
    price_relation = None
    shopping = plan.intent in {'new_search','refine_search','consultation','clarification'}
    for operation in plan.operations:
        field, action, value = operation.field, operation.op, operation.value
        if field in seen:
            raise InvalidDialoguePlan('Multiple operations on one field')
        seen.add(field)
        if action in {'KEEP','UNKNOWN'}:
            if value:
                raise InvalidDialoguePlan('Abstention must not carry a value')
            if action == 'UNKNOWN':
                pending_slot = field
            continue
        pending_evidence=False
        if pending and evidence_matches(pending.get('message',''),operation.evidence):
            pending_evidence=any(op.get('field')==field and op.get('op')==action
                                 and op.get('value')==value and op.get('evidence')==operation.evidence
                                 and op.get('exclusive',False)==operation.exclusive
                                 for op in pending.get('plan',{}).get('operations',[]))
        if not operation.evidence or not (evidence_matches(message, operation.evidence) or pending_evidence):
            raise InvalidDialoguePlan('Missing current-message quote')
        if not shopping and field not in {'references','pending_slot'}:
            raise InvalidDialoguePlan('Non-shopping intent must preserve shopping slots')
        if field == 'task':
            if action != 'RESET' or value or plan.intent != 'new_search':
                raise InvalidDialoguePlan('Invalid task reset')
            if not any(term in normalize(operation.evidence) for term in
                       ('nhu cau','dieu kien cu','bat dau','tim moi','khac hoan toan')):
                raise InvalidDialoguePlan('Whole-task reset is not evidenced')
            reset = True
            continue
        if action == 'RESET':
            raise InvalidDialoguePlan('RESET only applies to whole task')
        if field == 'references':
            if action != 'SET' or not re.fullmatch(r'[1-9]\d*(?:,[1-9]\d*)*', value):
                raise InvalidDialoguePlan('Invalid reference positions')
            references = tuple(int(v) for v in value.split(','))
            if len(references)>3 or len(set(references))!=len(references) or any(i>len(products) for i in references):
                raise InvalidDialoguePlan('Reference outside previous cards')
            continue
        if field == 'pending_slot':
            if action != 'SET' or value not in ShoppingState.__dataclass_fields__ and value != 'references':
                raise InvalidDialoguePlan('Invalid clarification field')
            pending_slot = value
            continue
        if field == 'price_relation':
            if action != 'SET' or value != 'cheaper':
                raise InvalidDialoguePlan('Unsupported comparison relation')
            price_relation = value
            continue
        if action == 'CLEAR':
            if value:
                raise InvalidDialoguePlan('CLEAR must not provide a replacement value')
            if field in {'top_k'}:
                raise InvalidDialoguePlan('Result count needs a valid value')
            if not _destructive_scope(field,operation.evidence,before):
                raise InvalidDialoguePlan('Destructive operation scope is unverified')
            clear.add(field)
            continue
        if action != 'SET':
            raise InvalidDialoguePlan('Unsupported operation')
        if field in {'category','material','gemstone','audience','style'}:
            if not _entity_grounded(field,value,operation.evidence,encoder):
                raise InvalidDialoguePlan('Unverified entity evidence')
            if not _positive_entity(field,value,message if not pending_evidence else pending['message']):
                raise InvalidDialoguePlan('Entity value is explicitly negated')
            if field in {'audience','style'} and (field,value) not in set(verified_attributes):
                raise InvalidDialoguePlan('Product preference lacks verified data')
            updates[field] = value
        elif field in {'min_price','max_price'}:
            try:
                if not _amount_grounded(value,operation.evidence):
                    raise InvalidDialoguePlan('Amount not supported by quote')
                amount=Decimal(value)
                from .dialogue_state_extractor import extract_state_changes
                from .retrieval import extract_price_filter
                known,_=extract_state_changes(message if not pending_evidence else pending['message'],extract_price_filter)
                if known.get(field) is not None:
                    if Decimal(str(known[field]))!=amount or known.get(field.replace('_price','_exclusive'),False)!=operation.exclusive:
                        raise InvalidDialoguePlan('Explicit price evidence contradicts semantic proposal')
                updates[field] = int(amount) if amount == int(amount) else format(amount,'f')
                updates[field.replace('_price','_exclusive')] = operation.exclusive
            except (InvalidOperation, ValueError):
                raise InvalidDialoguePlan('Invalid monetary evidence') from None
        elif field == 'top_k':
            if not value.isdigit() or not 1<=int(value)<=10 or not _count_grounded(value,operation.evidence):
                raise InvalidDialoguePlan('Invalid count evidence')
            updates[field] = int(value)
        elif field == 'price_preference':
            if value not in allowed_entities()[field]:
                raise InvalidDialoguePlan('Unknown preference')
            updates[field] = value
    if previous is not None and plan.intent == 'new_search' and not reset:
        raise InvalidDialoguePlan('New task requires explicit reset evidence')
    if plan.intent == 'refine_search' and previous is None:
        raise InvalidDialoguePlan('No prior shopping task')
    if pending_slot:
        # Atomicity: defer the complete request instead of silently applying its
        # understood subset. Pending plan is kept separately by the coordinator.
        return ValidatedDialoguePlan('clarification',before,tuple(plan.operations),references,pending_slot)
    if price_relation:
        selected = [products[i-1] for i in references] if references else list(products)
        if not selected:
            raise InvalidDialoguePlan('No grounded comparison anchor')
        try:
            prices=[Decimal(str(p['Price'])) for p in selected]
            if any(not p.is_finite() or p<0 for p in prices):
                raise InvalidDialoguePlan('Invalid reference price')
            anchor=min(prices)
        except (KeyError,InvalidOperation):
            raise InvalidDialoguePlan('Unverified reference price') from None
        current=updates.get('max_price',None if reset or 'max_price' in clear else before.max_price)
        if current is None or anchor<=Decimal(str(current)):
            clear.discard('max_price')
            updates.update(max_price=int(anchor) if anchor==int(anchor) else format(anchor,'f'),max_exclusive=True)
        updates['price_preference']='affordable'
    try:
        if reset:
            updates.setdefault('top_k',top_k)
        state=StatePatch(updates,frozenset(clear),reset).apply(before)
        from .dialogue_state_query import render_shopping_query
        query=render_shopping_query(state) if shopping else None
    except (ValueError,TypeError):
        raise InvalidDialoguePlan('Invalid resulting constraints') from None
    if plan.intent=='comparison' and len(references)<2:
        raise InvalidDialoguePlan('Comparison needs two selected cards')
    return ValidatedDialoguePlan(plan.intent,state,tuple(plan.operations),references,None,query)
