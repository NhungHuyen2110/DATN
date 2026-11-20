"""Preserve NFC for evidence; use a separate accent-folded form for matching."""

import re
import unicodedata


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", nfc(text).casefold().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w.,<>=#-]+", " ", text)
    text = re.sub(r"\b(vang(?: trang| hong)?)\s*(10|14|18|24)\s*k\b", r"\1 \2k", text)
    return " ".join(text.split())


def contains(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None
