"""Detect price preferences without inventing a budget."""

import re
from .entity_linking import normalize


PRICE_CONCEPTS = {
    'neutral': (
        r'\bkhong (?:can |qua )?quan tam (?:den |ve )?gia\b',
        r'\bgia nao cung duoc\b',
        r'\bkhong quan trong gia\b',
        r'\bkhong gioi han ngan sach\b',
    ),
    'lowest_price': (
        r'\bre nhat\b',
        r'\bgia thap nhat\b',
        r'\bgia tu thap den cao\b',
    ),
    'highest_price': (
        r'\bdat nhat\b',
        r'\bmac nhat\b',
        r'\bgia cao nhat\b',
        r'\bgia tu cao den thap\b',
    ),
    'affordable': (
        r'\bgia mem\b',
        r'\bgia re\b',
        r'\bvua tui tien\b',
        r'\bhop tui tien\b',
        r'\bbinh dan\b',
        r'\btiet kiem\b',
        r'\bkhong qua (?:dat|mac)\b',
        r'\bdung (?:dat|mac) qua\b',
        r'\bgia phai chang\b',
        r'\bgia sinh vien\b',
        r'\bgia thap\b',
    ),
}


def detect_price_preference(query):
    text = normalize(query)

    if re.search(
        r'\b(?:khong|chang)\s+'
        r'(?:(?:can|muon|thich|mua|tim|chon|lay|'
        r'san|pham|trang|suc|mon|do|loai|mau|qua)\s+){0,8}'
        r'(?:gia re|re nhat|dat nhat|mac nhat|'
        r'gia thap|gia mem|binh dan|tiet kiem|'
        r'vua tui tien|gia phai chang)\b',
        text
    ):
        return 'neutral'

    for preference, patterns in PRICE_CONCEPTS.items():
        if any(
            re.search(pattern, text)
            for pattern in patterns
        ):
            return preference

    return 'neutral'