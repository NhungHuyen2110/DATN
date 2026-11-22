"""Resolve explicit IDs/unique catalog names for related-product queries; no inferred product facts."""
import re
from .entity_linking import normalize
from shared.verified_attributes import reviews_enabled


def reference_request(query):
    text = normalize(query)
    requested = []
    if re.search(r'\bcung (?:loai )?da\b', text):
        requested.append('HAS_GEMSTONE')
    if re.search(r'\bcung chat lieu\b', text):
        requested.append('MADE_OF')
    if re.search(r'\bcung (?:danh muc|loai trang suc)\b', text):
        requested.append('BELONGS_TO')
    unsupported_style = bool(re.search(r'\bcung phong cach\b|\bphong cach tuong tu\b', text)
                             or (re.search(r'\bphong cach\b', text) and re.search(r'\b(?:cung|giong|tuong tu)\b', text)))
    active = bool(requested or unsupported_style or re.search(r'\b(?:giong|tuong tu)\b', text))
    if unsupported_style and reviews_enabled():
        requested.append('HAS_STYLE')
        unsupported_style = False
    return {'active': active, 'relations': requested, 'unsupported_style': unsupported_style}


def resolve_reference(query, catalog):
    ids = {int(value) for value in re.findall(r'\b(?:san pham|ma sp|sp|product|id)\s*[#:=]?\s*(\d+)\b', normalize(query))}
    if len(ids) > 1:
        return {'status': 'clarification_required', 'reason': 'multiple_reference_products'}
    if ids:
        pid = next(iter(ids))
        return {'status': 'ok', 'product': catalog[pid]} if pid in catalog else {'status': 'reference_unavailable'}
    text = ' ' + normalize(query) + ' '
    candidates = [(len(normalize(item['ProductName'])), pid) for pid, item in catalog.items()
                  if normalize(item['ProductName']) and ' ' + normalize(item['ProductName']) + ' ' in text]
    if candidates:
        longest = max(length for length, _ in candidates)
        matches = [pid for length, pid in candidates if length == longest]
        if len(matches) == 1:
            return {'status': 'ok', 'product': catalog[matches[0]]}
    return {'status': 'clarification_required', 'reason': 'reference_product_id_required'}
