"""Inventory grammar and renderer; filter in SQL before limiting results."""
import re
from .ai_inventory_tools import get_inventory_statistics
from .ai_staff_intent import normalize_text
from shared.conversation import task_body, scope_remainder
from .ai_multi_intent import INVENTORY_REQUEST


def inventory_scope(question):
    text = task_body(question)
    if not re.search(r'\b(?:' + INVENTORY_REQUEST + r')\b', text):
        return None
    threshold = re.search(r'\b(nguong(?: ton kho)?|toi da|khong qua|duoi|it hon)\s*(\d+)\b', text)
    value = int(threshold[2]) - (1 if threshold[1] in {'duoi', 'it hon'} else 0) if threshold else 5
    if threshold:
        text = text[:threshold.start()] + ' ' + text[threshold.end():]
    limit = re.search(r'\b(?:top|gioi han)\s*(\d+)\b', text)
    count = int(limit[1]) if limit else 20
    if limit:
        text = text[:limit.start()] + ' ' + text[limit.end():]
    mode = ('low_stock' if re.search(r'\bsap het\b', text) else
            'out_of_stock' if 'het hang' in text else 'in_stock' if 'con hang' in text else None)
    without_low = re.sub(r'\bsap het(?: hang)?\b', '', text)
    if 'het hang' in without_low and (mode == 'low_stock' or 'con hang' in text):
        return {'intent': 'unsupported', 'message': 'Hãy chọn một loại tồn kho; chưa hỗ trợ gộp nhiều loại trong một danh sách.'}
    if mode == 'in_stock' and threshold and threshold[1] in {'duoi', 'it hon', 'toi da', 'khong qua'}:
        mode = 'low_stock'
    residual = scope_remainder(text, [INVENTORY_REQUEST,
                                     r'thong ke|san pham|danh sach|liet ke|chiec|cai|va'])
    if not 0 <= value <= 1000 or not 1 <= count <= 50 or residual:
        return {'intent': 'unsupported', 'message': 'Chưa hỗ trợ đầy đủ bộ lọc tồn kho; hãy nêu loại tồn kho và ngưỡng 0–1000.'}
    return {'intent': 'inventory_statistics', 'mode': mode, 'threshold': value, 'limit': count,
            'explicit_threshold': threshold is not None, 'explicit_limit': limit is not None}


def answer_inventory_question(db, question: str):
    scope = inventory_scope(question)
    if scope is None:
        return None
    if scope['intent'] != 'inventory_statistics':
        return {'intent': scope['intent'], 'answer': scope['message'], 'data': None}
    mode = scope['mode']
    result = get_inventory_statistics(db=db, threshold=scope['threshold'], limit=scope['limit'], mode=mode)
    counts = {'out_of_stock': result['out_of_stock_products'], 'low_stock': result['low_stock_products'],
              'in_stock': result['total_products'] - result['out_of_stock_products']}
    label = {'out_of_stock': 'hết hàng', 'low_stock': 'sắp hết hàng', 'in_stock': 'còn hàng'}
    if mode:
        count = counts[mode]
        lines = [f"Hiện có {count} sản phẩm {label[mode]}; ngưỡng sắp hết: 1–{scope['threshold']}."]
    else:
        count = counts['out_of_stock'] + counts['low_stock']
        lines = [f"Tồn kho hiện tại: {result['total_products']} sản phẩm; hết hàng: {counts['out_of_stock']}; "
                 f"sắp hết hàng (1–{scope['threshold']}): {counts['low_stock']}."]
    for index, p in enumerate(result['products'], 1):
        lines.append(f"{index}. {p['product_name']} (SKU: {p['sku']}) - còn {p['stock']} chiếc.")
    if count > len(result['products']):
        lines.append(f"Đang hiển thị {len(result['products'])}/{count} sản phẩm.")
    if count and mode != 'in_stock':
        lines.append('Có thể kiểm tra kế hoạch bổ sung cho các sản phẩm này; chưa đủ dữ liệu để đề xuất số lượng nhập.')
    return {'intent': 'inventory_statistics', 'field': mode or 'summary', 'answer': '\n'.join(lines),
            'data': {**result, 'threshold': scope['threshold']}}
