"""Conservative public-chat routing; a claimed role never grants privileges."""
from .entity_linking import normalize


def classify_query(query):
    text = normalize(query)
    padded = ' ' + text + ' '
    def has(phrase):
        return ' ' + phrase + ' ' in padded
    if any(has(phrase) for phrase in ('gia von', 'loi nhuan', 'doanh thu', 'mat khau',
                                      'system prompt', 'reset token', 'bo qua huong dan',
                                      'ignore previous instructions', 'don hang cua nguoi khac')):
        return 'restricted_request'
    if text in {'xin chao', 'chao', 'chao ban', 'hello', 'hi', 'cam on', 'thank you'}:
        return 'greeting'
    if any(has(phrase) for phrase in ('phi van chuyen', 'phi ship', 'mien phi van chuyen',
                                      'chinh sach van chuyen', 'shipping fee')):
        return 'shipping_policy'
    if any(has(phrase) for phrase in ('bao hanh', 'doi tra', 'hoan tien')):
        return 'unverified_policy'
    if any(has(phrase) for phrase in ('don hang', 'ma don', 'tinh trang don')):
        return 'customer_order_guidance'
    if any(has(phrase) for phrase in ('thoi tiet', 'ket qua bong da', 'viet ma python', 'giai phuong trinh')):
        return 'out_of_scope'
    return 'product_search'
