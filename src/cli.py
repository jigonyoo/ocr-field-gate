import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import gate

def key(i):
    return (i.doc, i.fld, i.rule)

def main():
    src = os.environ.get("DOCS", "fixtures/invoices.json")
    out = os.environ.get("OUT", "out")
    os.makedirs(out, exist_ok=True)
    docs = gate.load(src)
    structural = gate.check(docs)
    conf = gate.confidence_only(docs)

    s_docs = {i.doc for i in structural}
    c_docs = {i.doc for i in conf}
    missed = sorted(s_docs - c_docs)
    only_conf = sorted(c_docs - s_docs)

    print(f"{len(docs)} documents, {len(docs)*6} fields\n")
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
    print(f"\nwrote {out}/report.md")

if __name__ == "__main__":
    main()
