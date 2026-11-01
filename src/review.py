"""Human review queue, one CSV row per supplied issue."""
import csv


def write_csv(stream, docs, issues):
    documents = {d["doc"]: d for d in docs}
    writer = csv.writer(stream)
    writer.writerow(["document_id", "field", "value", "rule", "confidence"])
    for issue in issues:
        value = documents[issue.doc]["fields"].get(issue.fld, {}).get("text", "")
        writer.writerow([issue.doc, issue.fld, value, issue.rule, issue.conf])
