
"""Extract supported shopping-state changes from Vietnamese messages."""

import re
from decimal import Decimal

from .entity_linking import link_query, normalize
from .shopping_advice import budget_text, standalone_budget
from .price_preference import detect_price_preference
from .dialogue_state import ShoppingState, update_state


ENTITY_FIELDS = {
    "Category": "category",
    "Gemstone": "gemstone",
    "Audience": "audience",
    "Style": "style",
}


MATERIALS = {
    "vang trang 18k": "white_gold_18k",
    "vang trang 14k": "white_gold_14k",
    "vang trang 10k": "white_gold_10k",
    "vang trang": "white_gold",
    "vang hong": "rose_gold",
    "vang 18k": "gold_18k",
    "vang 24k": "gold_24k",
    "vang 14k": "gold_14k",
    "vang 10k": "gold_10k",
    "bac 925": "silver",
    "bach kim": "platinum",
    "platinum": "platinum",
    "bac": "silver",
    "vang": "gold",
}


def extract_state_changes(message, parse_price):

    if not isinstance(message, str):
        raise TypeError("Expected text message")

    text = normalize(message)
    updates = {}
    clear = set()

    material_negation = re.compile(
        r"\b(?:khong can|khong bat buoc|bo yeu cau)"
        r"\s+(?:bang |chat lieu )?"
        r"(?:bac(?: 925)?|vang(?: trang| hong| 18k)?|"
        r"bach kim|platinum|chat lieu)"
        r"(?: nua)?\b")
    clear_material = bool(material_negation.search(text))

    if clear_material:
        clear.add("material")
    material_text = re.split(r'\b(?:thay vi|chu khong phai)\b', material_negation.sub(' ', text))[0]
    found_materials = set()
    for alias, canonical in sorted(MATERIALS.items(), key=lambda item: -len(item[0])):
        if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", material_text):
            found_materials.add(canonical)
            material_text = re.sub(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', ' ', material_text)
    if len(found_materials) > 1:
        raise ValueError('Ambiguous material selection')
    if found_materials:
        updates['material'] = found_materials.pop()
        clear.discard('material')

    entity_text = re.split(r"\b(?:thay vi|chu khong phai)\b", text)[0]
    from .entity_linking import load_entities
    for entity in load_entities()['entities']:
        if entity['label'] != 'Gemstone':
            continue
        for alias in entity['aliases']:
            pattern = r'\b(?:khong can|bo yeu cau)\s+(?:da\s+)?' + re.escape(normalize(alias)) + r'(?: nua)?\b'
            if re.search(pattern, entity_text):
                clear.add('gemstone')
                entity_text = re.sub(pattern, ' ', entity_text)
    understanding = link_query(entity_text)

    if not understanding.get("needs_clarification"):
        grouped = {}

        for entity in understanding.get("entities", []):
            field = ENTITY_FIELDS.get(entity["label"])

            if field:
                grouped.setdefault(field, set()).add(
                    entity["canonical_id"]
                )

        for field, values in grouped.items():
            if len(values) == 1:
                updates[field] = next(iter(values))
                clear.discard(field)

    price_query = standalone_budget(message) or budget_text(message)

    price_query = re.sub(
        r"\b(?:ngân sách|ngan sach)\s+(?:(?:của tôi|cua toi|của mình|cua minh)\s+)?"
        r"(?:(?:là|la)\s+)?(?:lên|len|còn|con|xuống|xuong)\s+",
        "ngân sách ", price_query, flags=re.I)

    price_query = re.sub(
        r"\b(?:tăng|giảm)\s+(?:ngân sách\s+)?"
        r"(?:lên|xuống)\s+",
        "ngân sách ",
        price_query,
        flags=re.I
    )

    price_aliases = {
        "duoi": "dưới",
        "tren": "trên",
        "tu": "từ",
        "den": "đến",
        "tam": "tầm",
        "khoang": "khoảng",
        "trieu": "triệu",
        "nghin": "nghìn",
        "ngan": "ngàn",
        "dong": "đồng",
        "khong qua": "không quá",
        "ngan sach": "ngân sách",
        "toi da": "tối đa",
    }

    price_query = re.sub(
        r"(?<!\w)(?:"
        + "|".join(
            re.escape(alias)
            for alias in sorted(
                price_aliases, key=len, reverse=True
            )
        )
        + r")(?!\w)",
        lambda match: price_aliases[match.group(0).lower()],
        price_query,
        flags=re.I
    )

    prices = parse_price(price_query) or {}

    for field in ("min_price", "max_price"):
        value = prices.get(field)

        if value is not None:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise ValueError("Invalid budget")
            updates[field] = int(amount) if amount == int(amount) else format(amount, 'f')

            exclusive = field.replace(
                "_price", "_exclusive"
            )

            normalized_price = normalize(price_query)

            if exclusive in prices:
                updates[exclusive] = bool(prices[exclusive])

            elif field == "max_price":
                updates[exclusive] = bool(re.search(
                    r"\b(?:duoi|nho hon|thap hon)\s+\d",
                    normalized_price
                ))

            else:
                updates[exclusive] = bool(re.search(
                    r"\b(?:tren|lon hon|cao hon)\s+\d",
                    normalized_price
                ))

    preference = detect_price_preference(message)

    if preference != "neutral":
        updates["price_preference"] = preference

    elif re.search(
        r"\b(?:khong quan tam gia|"
        r"khong can uu tien (?:gia re|gia thap|gia mem)|"
        r"bo (?:uu tien gia|so thich gia)|"
        r"gia nao cung duoc|"
        r"khong quan trong gia|"
        r"tien bac khong thanh van de)\b",
        text
    ):
        clear.add("price_preference")

    numbers = {'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4, 'nam': 5,
               'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10}
    number_pattern = r"\d{1,2}|" + '|'.join(numbers)
    count = re.search(r"\btop\s*(\d{1,2})\b", text) or re.search(
        r"\b(" + number_pattern + r")\s+(?:mau|mon|san pham|ket qua)\b", text)

    if count:
        value = count.group(1)
        updates["top_k"] = int(value) if value.isdigit() else numbers[value]

    if re.search(r'\b(?:khong|chang|dung)\s+(?:can\s+)?uu tien\s+(?:gia re|gia thap|gia mem)\b', text):
        updates.pop('price_preference', None)
        clear.add('price_preference')

    for field, phrase in (("gemstone", r"(?:da|da quy|loai da)"),
                          ("material", r"(?:chat lieu)")):
        if re.search(r"\b(?:khong can|bo|khong gioi han)\s+(?:yeu cau\s+)?" + phrase + r"\b", text):
            clear.add(field)
            updates.pop(field, None)
    if re.search(r"\b(?:bo|khong gioi han|khong can gioi han)\s+(?:ngan sach|gia)\b(?!\s+(?:san|tran|toi thieu|toi da)\b)", text):
        clear.update(('min_price', 'max_price'))
        for field in ('min_price', 'max_price', 'min_exclusive', 'max_exclusive'):
            updates.pop(field, None)

    for field, scope in (('min_price', r'(?:gia san|muc gia toi thieu|gia toi thieu)'),
                         ('max_price', r'(?:gia tran|muc gia toi da|gia toi da)')):
        if re.search(r'\b(?:bo|go|xoa|khong can)\s+' + scope + r'\b', text):
            clear.add(field)
            updates.pop(field, None)
            updates.pop(field.replace('_price', '_exclusive'), None)

    return updates, clear


def apply_shopping_message(
    state, message, parse_price
):
    """Apply changes to an already-established shopping task."""

    if not isinstance(state, ShoppingState):
        raise TypeError("Expected ShoppingState")

    updates, clear = extract_state_changes(
        message, parse_price
    )

    return update_state(
        state,
        updates=updates,
        clear=clear
    )
