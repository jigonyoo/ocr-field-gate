"""Field-level verification for OCR output.

The premise: confidence is not accuracy. A recognition engine reports how sure it is
about the shapes it saw, not whether the value is right. So the gate checks structure -
arithmetic, format, character class, uniqueness - and uses confidence only as one more
signal, never as the decision."""
import re, json
from dataclasses import dataclass, field

CONF_FLOOR = 0.90
MONEY = re.compile(r"^\d+(\.\d{2})?$")
DATEF = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
# characters an engine confuses with digits
CONFUSED = {"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8", "Z": "2"}
NUMERIC_FIELDS = ("subtotal", "tax", "total")
REQUIRED = ("invoice_no", "date", "subtotal", "tax", "total", "vendor")

@dataclass
class Issue:
    doc: str
    fld: str
    rule: str
    detail: str
    conf: float
    repairable: bool = False
    suggestion: str = ""

def _money(s):
    try:
        return round(float(s), 2)
    except (TypeError, ValueError):
        return None

def _demangle(s):
    return "".join(CONFUSED.get(c, c) for c in s)

def check(docs):
    issues, seen = [], {}
    for d in docs:
        doc, f = d["doc"], d["fields"]
        g = lambda k: f.get(k, {}).get("text", "")
        c = lambda k: f.get(k, {}).get("conf", 0.0)

        for k in REQUIRED:
            if not g(k).strip():
                issues.append(Issue(doc, k, "missing", "required field is empty", c(k)))

        # character-class: a numeric field containing a letter an engine confuses for a digit
        for k in NUMERIC_FIELDS:
            v = g(k)
            if v and not MONEY.match(v):
                fixed = _demangle(v)
                if MONEY.match(fixed):
                    issues.append(Issue(doc, k, "confused_character",
                        f"{v!r} is not a number; letters here are confused with digits",
                        c(k), True, fixed))
                else:
                    issues.append(Issue(doc, k, "not_a_number", f"{v!r}", c(k)))

        # arithmetic: the invoice checks itself
        sub, tax, tot = (_money(_demangle(g(k))) for k in NUMERIC_FIELDS)
        if None not in (sub, tax, tot) and round(sub + tax, 2) != tot:
            issues.append(Issue(doc, "total", "arithmetic",
                f"subtotal {sub} + tax {tax} = {round(sub+tax,2)}, document says {tot}",
                c("total")))

        # format: a date that is not a date
        m = DATEF.match(g("date"))
        if g("date") and not m:
            issues.append(Issue(doc, "date", "format", f"{g('date')!r} is not YYYY-MM-DD", c("date")))
        elif m:
            y, mo, dd = (int(x) for x in m.groups())
            if not (1 <= mo <= 12) or not (1 <= dd <= 31):
                issues.append(Issue(doc, "date", "impossible_date",
                    f"month {mo}, day {dd}", c("date")))

        # uniqueness across the batch
        inv = g("invoice_no")
        if inv:
            if inv in seen:
                issues.append(Issue(doc, "invoice_no", "duplicate",
                    f"already used by {seen[inv]}", c("invoice_no")))
            else:
                seen[inv] = doc
    return issues

def confidence_only(docs, floor=CONF_FLOOR):
    """The gate a lot of pipelines actually ship: threshold the confidence and move on."""
    out = []
    for d in docs:
        for k, v in d["fields"].items():
            if v.get("conf", 0) < floor:
                out.append(Issue(d["doc"], k, "low_confidence",
                                 f"conf {v['conf']:.2f} below {floor}", v["conf"]))
    return out

def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
