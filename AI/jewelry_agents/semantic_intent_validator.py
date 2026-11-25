
"""Validate semantic intent proposals before retrieval."""

import re
import unicodedata
from difflib import SequenceMatcher


ALLOWED_LABELS = {
    "neutral",
    "affordable",
    "lowest_price",
    "highest_price",
}


def normalize_text(value):
    text = unicodedata.normalize("NFC", value).casefold()
    return " ".join(re.findall(r"\w+", text))


def evidence_matches(query, evidence):
    query = normalize_text(query)
    evidence = normalize_text(evidence)

    if not evidence:
        return False

    query_tokens = query.split()
    evidence_tokens = evidence.split()

    if " " + evidence + " " in " " + query + " ":
        return True

    # Small omissions in longer quotations.
    if len(evidence_tokens) < 5:
        return False

    size = len(evidence_tokens)

    for width in range(size, size + 2):
        for start in range(len(query_tokens) - width + 1):
            window = query_tokens[start:start + width]

            matcher = SequenceMatcher(
                None,
                evidence_tokens,
                window,
                autojunk=False
            )

            changes = [
                item for item in matcher.get_opcodes()
                if item[0] != "equal"
            ]

            # Only one omitted, non-semantic filler word.
            if len(changes) != 1:
                continue

            tag, a, b, c, d = changes[0]

            if (
                tag == "insert"
                and d - c == 1
                and window[c] in {"rồi", "thì", "nhé", "ạ"}
                and matcher.ratio() >= 0.88
            ):
                return True

    return False


def budget_only_evidence(evidence):
    text = normalize_text(evidence)

    return bool(re.fullmatch(
        r"(?:(?:dưới|trên|tầm|khoảng|từ|đến|"
        r"ngân sách|tối đa|không quá)\s+)*"
        r"\d+(?:\s+\d+)*\s*"
        r"(?:triệu|tr|nghìn|ngàn|k|vnd|đồng)",
        text
    ))


def demographic_only_evidence(evidence):
    text = normalize_text(evidence)

    return text in {
        "sinh viên",
        "học sinh",
        "nhân viên",
        "nhân viên văn phòng",
        "người đi làm",
        "nam",
        "nữ",
        "người trẻ",
        "người cao tuổi",
        "trẻ em",
    }


def validate_price_intent(query, proposal):
    if not isinstance(proposal, dict):
        return "neutral"

    label = proposal.get("price_preference")
    evidence = proposal.get("evidence", "")

    if not isinstance(label, str):
        return "neutral"

    if label not in ALLOWED_LABELS:
        return "neutral"

    if not isinstance(evidence, str):
        return "neutral"

    if label == "neutral":
        return "neutral"

    if not evidence_matches(query, evidence):
        return "neutral"

    if budget_only_evidence(evidence):
        return "neutral"

    if demographic_only_evidence(evidence):
        return "neutral"

    return label
