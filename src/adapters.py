"""Offline adapters. Bounding boxes are [left, top, width, height]."""
import csv
import io
import math


def _field(text, confidence, box):
    confidence = float(confidence)
    box = [float(x) for x in box]
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if len(box) != 4 or not all(math.isfinite(x) for x in box) or min(box[2:]) < 0:
        raise ValueError("invalid bbox")
    return {"text": str(text), "conf": confidence, "bbox": box}


def from_json(document):
    """Accept {id, fields: [{name, value, confidence, bbox}]}."""
    fields = {}
    for entry in document["fields"]:
        name = entry["name"]
        if name in fields:
            raise ValueError("duplicate field: " + name)
        fields[name] = _field(entry["value"], entry["confidence"], entry["bbox"])
    return {"doc": document["id"], "fields": fields}


def from_tesseract_tsv(tsv, doc_id, regions):
    """Map word centers into caller-supplied field regions; preserve TSV order.

    Confidence is the minimum word confidence / 100; bbox is the word union.
    Empty fields have confidence zero. Ambiguous region matches are rejected.
    """
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t")
    required = {"level", "conf", "left", "top", "width", "height", "text"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("missing TSV columns")
    words = {name: [] for name in regions}
    for row in reader:
        if int(row["level"]) != 5 or float(row["conf"]) < 0 or not row["text"].strip():
            continue
        word = _field(row["text"], float(row["conf"]) / 100,
                      [row[k] for k in ("left", "top", "width", "height")])
        x, y, w, h = word["bbox"]
        matches = [name for name, (l, t, rw, rh) in regions.items()
                   if l <= x + w / 2 < l + rw and t <= y + h / 2 < t + rh]
        if len(matches) > 1:
            raise ValueError("overlapping field regions")
        if matches:
            words[matches[0]].append(word)
    fields = {}
    for name, entries in words.items():
        if not entries:
            fields[name] = _field("", 0, regions[name])
            continue
        left = min(e["bbox"][0] for e in entries)
        top = min(e["bbox"][1] for e in entries)
        right = max(e["bbox"][0] + e["bbox"][2] for e in entries)
        bottom = max(e["bbox"][1] + e["bbox"][3] for e in entries)
        fields[name] = _field(" ".join(e["text"] for e in entries),
                              min(e["conf"] for e in entries),
                              [left, top, right - left, bottom - top])
    return {"doc": doc_id, "fields": fields}
