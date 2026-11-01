"""Opt-in taxable Korean invoice profile; leaves gate.check unchanged."""
import re
from datetime import date
from gate import Issue


def valid_business_number(value):
    if not re.fullmatch(r"[0-9]{10}", value):
        return False
    digits = list(map(int, value))
    weighted = sum(a * b for a, b in zip(digits[:9], (1, 3, 7, 1, 3, 7, 1, 3, 5)))
    return (10 - (weighted + digits[8] * 5 // 10) % 10) % 10 == digits[9]


def check(docs):
    issues = []
    for doc in docs:
        fields = doc["fields"]
        def text(name):
            return fields.get(name, {}).get("text", "")
        def issue(name, rule, detail):
            issues.append(Issue(doc["doc"], name, rule, detail,
                                fields.get(name, {}).get("conf", 0)))
        if not valid_business_number(text("business_no")):
            issue("business_no", "business_checksum", "requires 10 ASCII digits and valid checksum")
        value = text("date")
        if not re.fullmatch(r"[0-9]{4}([-\.])[0-9]{2}\1[0-9]{2}", value):
            issue("date", "kr_date", "requires YYYY-MM-DD or YYYY.MM.DD")
        else:
            try:
                date.fromisoformat(value.replace(".", "-"))
            except ValueError:
                issue("date", "kr_date", "invalid calendar date")
        def won(name):
            value = text(name)
            if not re.fullmatch(r"[0-9]+", value):
                issue(name, "kr_won", "requires nonnegative integer won")
                return None
            return int(value)
        sub, tax, total = (won(name) for name in ("subtotal", "tax", "total"))
        if None not in (sub, tax, total) and sub + tax != total:
            issue("total", "kr_total", "subtotal + tax must equal total (zero tolerance)")
        if sub is not None and tax is not None:
            expected = (sub + 5) // 10
            if tax != expected:
                issue("tax", "kr_vat", f"expected {expected} won (10%, half up, zero tolerance)")
        names = sorted(name for name in fields if re.fullmatch(r"item\.[0-9]+\.amount", name))
        if not names:
            issue("items", "kr_items_missing", "at least one item amount required")
        else:
            amounts = [won(name) for name in names]
            if sub is not None and all(a is not None for a in amounts) and sum(amounts) != sub:
                issue("subtotal", "kr_items_sum", "item amounts must sum to subtotal (zero tolerance)")
    return issues
