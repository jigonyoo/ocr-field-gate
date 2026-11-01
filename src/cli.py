import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import gate
import argparse
import adapters
import korean_invoice
import review

def key(i):
    return (i.doc, i.fld, i.rule)

def main():
    parser = argparse.ArgumentParser(description="Offline OCR field verification")
    parser.add_argument("--input", default=os.environ.get("DOCS", "fixtures/invoices.json"))
    parser.add_argument("--format", choices=("native", "json", "tsv"), default="native")
    parser.add_argument("--profile", choices=("legacy", "kr"), default="legacy")
    parser.add_argument("--regions", help="JSON object mapping field names to TSV bounding boxes")
    parser.add_argument("--doc-id", default="TSV-DOCUMENT")
    args = parser.parse_args()
    src = args.input
    out = os.environ.get("OUT", "out")
    os.makedirs(out, exist_ok=True)
    if args.format == "tsv":
        if not args.regions:
            parser.error("--regions is required for TSV")
        with open(src, encoding="utf-8") as stream:
            docs = [adapters.from_tesseract_tsv(stream.read(), args.doc_id, gate.load(args.regions))]
    elif args.format == "json":
        payload = gate.load(src)
        entries = payload["documents"] if isinstance(payload, dict) else payload
        docs = [adapters.from_json(d) for d in entries]
    else:
        docs = gate.load(src)
    structural = korean_invoice.check(docs) if args.profile == "kr" else gate.check(docs)
    conf = gate.confidence_only(docs)

    s_docs = {i.doc for i in structural}
    c_docs = {i.doc for i in conf}
    missed = sorted(s_docs - c_docs)
    only_conf = sorted(c_docs - s_docs)

    print(f"{len(docs)} documents, {sum(len(d['fields']) for d in docs)} fields\n")
    print(f"confidence-only gate (floor {gate.CONF_FLOOR})   flagged {len(conf)} fields "
          f"in {len(c_docs)} documents")
    print(f"structural gate                        flagged {len(structural)} fields "
          f"in {len(s_docs)} documents\n")
    print("real defects the confidence gate never saw:")
    for d in missed:
        for i in [x for x in structural if x.doc == d]:
            print(f"  {d}  {i.rule:<20} conf {i.conf:.2f}  {i.detail}")
    print("\nflagged by confidence but structurally sound:")
    for d in only_conf:
        print(f"  {d}  " + ", ".join(f"{i.fld} {i.conf:.2f}" for i in conf if i.doc == d))

    auto = [i for i in structural if i.repairable]
    human = [i for i in structural if not i.repairable]
    print(f"\nrepairable with evidence   {len(auto)}")
    print(f"must go to a person        {len(human)}")

    L = ["# OCR field gate", "", f"{len(docs)} documents.", "",
         "## Repairable — the arithmetic confirms the repair", ""]
    for i in auto:
        L += [f"- `{i.doc}` `{i.fld}` — {i.detail}. Suggested: `{i.suggestion}` "
              f"(confidence was {i.conf:.2f})"]
    L += ["", "## Needs a person", ""]
    for i in human:
        L += [f"- `{i.doc}` `{i.fld}` **{i.rule}** — {i.detail} (confidence {i.conf:.2f})"]
    with open(f"{out}/report.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    with open(f"{out}/review.csv", "w", encoding="utf-8", newline="") as fh:
        review.write_csv(fh, docs, human + conf)
    print(f"\nwrote {out}/report.md")

if __name__ == "__main__":
    main()
