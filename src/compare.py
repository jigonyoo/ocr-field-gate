"""Document-level confusion counts against fixture labels, never gate-derived labels."""
import gate
import korean_invoice


def comparison(docs, labels):
    rows = []
    for name, issues in (("confidence-only", gate.confidence_only(docs)),
                         ("Korean structural", korean_invoice.check(docs))):
        flagged = {i.doc for i in issues}
        tp = sum(bad and doc in flagged for doc, bad in labels.items())
        fp = sum(not bad and doc in flagged for doc, bad in labels.items())
        fn = sum(bad and doc not in flagged for doc, bad in labels.items())
        tn = sum(not bad and doc not in flagged for doc, bad in labels.items())
        rows.append(f"| {name} | {tp} | {fp} | {fn} | {tn} |")
    return "\n".join(["| gate | TP | FP | FN | TN |", "|---|---:|---:|---:|---:|", *rows])
