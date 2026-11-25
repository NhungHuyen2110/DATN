"""Advice is a preference, not an assertion that a product has a graph fact."""
import re
import unicodedata
from .entity_linking import link_query, normalize

STYLE_GUIDES = {
    'elegant': 'Với gu thanh lịch, bạn có thể bắt đầu từ dây chuyền, bông tai hoặc nhẫn rồi ưu tiên kiểu dáng gọn, ít chi tiết để dễ phối đồ.',
    'minimalist': 'Nếu thích tối giản, bạn có thể cân nhắc một món làm điểm nhấn, kiểu dáng gọn và ít chi tiết thay vì phối nhiều món cùng lúc.',
    'refined': 'Nếu muốn vẻ tinh tế, hãy cân nhắc tỷ lệ món trang sức với trang phục và sở thích người đeo; không nhất thiết phải chọn món đắt nhất.',
}
_MONEY = re.compile(r'(?:(?:dưới|duoi|trên|tren|từ|tu|đến|den|ngân\s+sách|ngan\s+sach|tầm|tam|khoảng|khoang|budget)\s*)?\d+(?:[.,]\d+)*\s*(?:triệu|trieu|tr|nghìn|nghin|ngàn|ngan|vnd|đồng|dong|₫)(?=\s|$|[,.!?])', re.I)


def budget_text(query):
    text = unicodedata.normalize('NFC', query)
    if re.search(r'\b(?:sku|ma san pham|ma hang|ma sp)\b', normalize(text)):
        return text
    text=re.sub(r'\b(?:đừng|dung)(?:\s+vượt)?\s+quá(?=\s+\d)', 'không quá',text,flags=re.I)
    cues={'duoi':'dưới','tren':'trên','tam':'tầm','khoang':'khoảng'}
    text=re.sub(r'\b(duoi|tren|tam|khoang|dưới|trên|tầm|khoảng)(?=\d)',
                lambda match:cues.get(match.group(1).lower(),match.group(1))+' ',text,flags=re.I)
    text = re.sub(r'(?<!\w)(\d+(?:[.,]\d+)?)\s*tr\b', r'\1 triệu', text, flags=re.I)
    # “18K” remains a material unless it occurs in an explicit price phrase.
    text = re.sub(r'((?:dưới|duoi|trên|tren|tầm|tam|khoảng|khoang|ngân sách|ngan sach|budget)\s*)(\d+(?:[.,]\d+)?)\s*k\b',
                  r'\1\2 nghìn', text, flags=re.I)
    if re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*k\s*', text, flags=re.I):
        text = re.sub(r'k\s*$', ' nghìn', text, flags=re.I)
    return text


def strict_preference_request(query):
    text = normalize(query)
    return bool(re.search(r'\b(?:top\s*\d+|bat buoc|chinh xac|phai co|da xac nhan|loc|cung|giong|tuong tu)\b', text)
            or re.search(r'\bchi\s+(?:lay|chon|tim|nhung|san pham|mau|goi y|cac)\b', text))


def advisory_request(query):
    understanding = link_query(query)
    if understanding['needs_clarification'] or strict_preference_request(query):
        return False
    text=normalize(query)
    preferences = [e for e in understanding['entities'] if e['label'] in {'Audience', 'Style'}]
    cues = ('chon gi', 'nen chon', 'tu van', 'goi y', 'nen mua', 'hop voi', 'thich gi')
    return bool(preferences and (any(cue in text for cue in cues) or
                text in {'thanh lich','toi gian','tinh te','nu thanh lich','cho nu','nu'}))


def standalone_budget(message):
    """A price-only message is a shopping constraint, even after session expiry."""
    text = budget_text(message)
    if len(text) > 100 or not _MONEY.search(text):
        return None
    remainder = normalize(_MONEY.sub(' ', text)).split()
    allowed = {'toi','minh','em','co','chi','tam','khoang','ngan','sach','duoi','tren',
               'tu','den','thoi','nhe','a','la','va','muc','gia','budget','duoc','khong','qua','da'}
    if any(word not in allowed for word in remainder):
        return None
    if not re.search(r'\b(?:duoi|tren|tu|den|khong qua|toi da|ngan sach|budget|tam|khoang|gia)\b',normalize(text)):
        text='ngân sách '+text
    return 'Tìm trang sức '+text


def advice_intro(query):
    entities = link_query(query)['entities']
    styles = [e['canonical_id'] for e in entities if e['label'] == 'Style']
    if styles:
        return STYLE_GUIDES.get(styles[0], '')
    return 'Mình sẽ chọn theo sở thích, dịp sử dụng và ngân sách, thay vì chỉ dựa vào giới tính người nhận.'


def next_question(query):
    if _MONEY.search(query) and any(e['label']=='Category' for e in link_query(query)['entities']):
        return 'Mình vẫn giữ giới hạn giá này nếu bạn muốn đổi loại trang sức để so sánh.'
    return ('Bạn muốn chi khoảng bao nhiêu?' if not _MONEY.search(query)
            else 'Bạn thích nhẫn, dây chuyền hay bông tai hơn?')



def remove_ontology_location(query):
    """Remove supported old wearing-location descriptions."""

    locations = (
        r"(?:ngón tay|ngón áp út|ngón trỏ|ngón cái|"
        r"ngón út|ngón giữa|cổ tay|vùng cổ|cổ|"
        r"vành tai|dái tai|tai)"
    )

    pattern = (
        r"(?<!\w)(?:đeo|ôm|trang trí)\s+"
        r"(?:(?:quanh|trên|ở|vào)\s+)?"
        + locations +
        r"(?!\w)"
    )

    result = re.sub(
        pattern, " ", query, flags=re.I
    )

    return " ".join(result.split())


def followup_query(message, previous):
    """Carry a short budget refinement forward; never inherit an unrelated topic."""
    if previous and len(message)<=100:
        entities=link_query(message)['entities']
        if len(entities)==1 and entities[0]['label'] in {'Category','Gemstone'}:
            selected=entities[0]
            fragment=budget_text(message)
            # leftover=normalize(_MONEY.sub(' ',fragment)).replace(normalize(selected['alias']),' ').split()
            alias = selected.get('alias')

            normalized_fragment = normalize(
                _MONEY.sub(' ', fragment)
            )

            if alias:
                normalized_fragment = normalized_fragment.replace(
                    normalize(alias), ' '
                )

            leftover = normalized_fragment.split()
            if set(leftover).issubset({'toi','minh','em','thich','chon','loai','lay','muon','cho','xin','thoi','nhe','a',
                                      'doi','sang','ngan','sach','chi','co','duoi','tam','khoang','gia','qua','da','di','chuyen','thay'}):
                base=previous

                if selected['label'] == 'Category':
                    old_categories = [
                        entity
                        for entity in link_query(previous)['entities']
                        if entity['label'] == 'Category'
                    ]

                    if any(
                        entity.get('method') == 'ontology_constraint'
                        for entity in old_categories
                    ):
                        base = remove_ontology_location(base)

                for old in link_query(base)['entities']:
                    if old['label']==selected['label'] and old.get('alias'):
                        # for alias in {old['alias'],normalize(old['alias'])}:
                        for alias in (
                            {old['alias'], normalize(old['alias'])}
                            if old.get('alias') else set()
):
                            base=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',' ',base,flags=re.I)
                if _MONEY.search(fragment):
                    base=_MONEY.sub(' ',budget_text(base))
                    if not re.search(r'\b(?:duoi|tren|tu|den|ngan sach|tam|khoang|gia|khong qua|toi da)\b',normalize(fragment)):
                        fragment=_MONEY.sub(lambda match:'ngân sách '+match.group(0),fragment)
                merged=' '.join((base+' '+fragment).split())
                return merged if len(merged)<=1000 else message
    normalized_message = budget_text(message)
    if not previous or len(message) > 100 or not _MONEY.search(normalized_message):
        return message
    text = normalize(message)
    remaining = normalize(_MONEY.sub(' ', normalized_message)).split()
    fillers = {'toi','minh','em','co','chi','tam','khoang','ngan','sach','duoi','tren','tu','den',
               'thoi','nhe','a','la','va','len','tang','giam','xuong','vay','muc','gia','max',
               'budget','duoc','khong','qua','da'}
    if any(token not in fillers and not token.isdigit() for token in remaining):
        return message
    if link_query(message)['entities'] or any(word in text for word in
            ('don hang', 'doanh thu', 'mat khau', 'phi ship', 'tai sao', 'top', 'san pham', 'sku')):
        return message
    if (not any(token.isdigit() for token in remaining)
            and not re.search(r'\b(?:duoi|tren|tu|den|khong qua|toi da|ngan sach|budget|tam|khoang|gia)\b', normalize(normalized_message))):
        normalized_message=_MONEY.sub(lambda match:'ngân sách '+match.group(0),normalized_message)
    base = _MONEY.sub(' ', budget_text(previous))
    merged = ' '.join((base + ' ' + normalized_message).split())
    return merged if len(merged) <= 1000 else message
