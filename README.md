# ocr-field-gate

**Confidence is not accuracy.** A recognition engine reports how sure it is about the *shapes* it
saw, not whether the *value* is right. This gate checks the structure instead — arithmetic, format,
character class, uniqueness — and uses confidence as one more signal, never as the decision.

```
make demo    # runs both gates over the same batch
make test    # offline standard-library tests
```

## The measured run

8 invoices, 48 fields.

| gate | fields flagged | documents flagged |
|---|---:|---:|
| confidence threshold ≥ 0.90 | 4 | 2 |
| structural | 5 | 5 |

**Four real defects were invisible to the confidence gate:**

| document | defect | confidence |
|---|---|---:|
| `INV-1002` | subtotal 800 + tax 160 = 960, document says **860** | 0.97 |
| `INV-1004` | date is **2026-13-02** — month 13 | 0.94 |
| `INV-1005` | subtotal reads **`l500.00`** — lowercase L, not a one | **0.99** |
| `INV-1007` | invoice number **duplicates `INV-1002`** | 0.98 |

And the one document the confidence gate *did* flag — `INV-1003`, three fields under 0.90 — is
structurally sound. Its low scores came from a genuinely smudged scan that the engine read correctly.

**The highest-confidence bad field in the batch scored 0.99.** A test asserts that, because it is
the entire argument: a threshold tuned to catch it would reject most of the good data too.

## What the arithmetic buys you

`INV-1005` is the only issue marked repairable, and only because the invoice checks itself:
`l500.00` demangles to `1500.00`, and 1500 + 300 = 1800, which is what the total says. The repair
is not proposed because a rule says L looks like 1 — it is proposed because **the document
corroborates it**.

Everything else goes to a person:

- an arithmetic mismatch could be a misread subtotal, a misread total, or a genuinely wrong invoice
- a missing vendor is reported, never filled in
- a duplicate invoice number might be a re-scan or might be a real duplicate payment

```
repairable with evidence   1
must go to a person        4
```

## Honest limits

- This runs on **simulated engine output**, not on images. There is no Tesseract or Textract here;
  the fixture is what an engine emits (per-field text plus a confidence). Swapping in a real engine
  changes the input, not the gate.
- The confused-character map is Latin-script and short: `O o l I S B Z`. It will not help with
  handwriting, other scripts, or a genuinely ambiguous glyph.
- Arithmetic checking assumes subtotal + tax = total. Discounts, multi-rate tax, rounding rules and
  foreign currency all break that assumption and would need their own rules.
- Uniqueness is checked within the batch only. A duplicate against last month's batch is not visible.
- 8 documents is a fixture, not a benchmark. The counts describe this fixture.

## Layout

```
fixtures/invoices.json   8 documents, 6 planted defects, engine-style confidences
src/gate.py              structural checks, plus the confidence-only gate for comparison
src/cli.py               the comparison table and out/report.md
tests/                   legacy rules, adapters, Korean profile, CSV and measured comparison
```

## OCR adapters and Korean electronic tax invoices

No OCR engine is installed or executed. Both adapters consume engine output and return
the existing `{doc, fields: {name: {text, conf, bbox}}}` shape. Coordinates are
`[left, top, width, height]` in source image units; confidences are normalized to [0, 1].

- `adapters.from_json(document)` accepts `{id, fields: [{name, value, confidence, bbox}]}`.
  Field names are explicit, values become text, and duplicate names are rejected.
  `fixtures/korean_invoices.json` contains synthetic examples of this format and labels.
- `adapters.from_tesseract_tsv(tsv, doc_id, regions)` accepts Tesseract TSV headers,
  including level, conf, left, top, width, height and text. It uses level-5 words only,
  skips negative-confidence and blank entries, and assigns words by their center to
  caller-supplied field regions. Overlapping matches fail instead of guessing.
  Text follows TSV order, confidence is the minimum word confidence divided by 100,
  and coordinates enclose all matched words. Empty regions yield empty text/confidence 0;
  unmatched words are ignored. Layout/reading-order discovery is outside this adapter.
  `fixtures/tesseract.tsv` and `fixtures/tesseract_regions.json` are synthetic examples.

Select the Korean profile explicitly; `gate.check` and the default legacy profile retain
their existing validation semantics. The Korean profile uses these canonical fields:

| field | validation |
|---|---|
| `business_no` | Exactly 10 ASCII digits. First nine weights: 1,3,7,1,3,7,1,3,5; add floor(ninth digit × 5 / 10); last digit must equal (10 − sum mod 10) mod 10. |
| `date` | YYYY-MM-DD or YYYY.MM.DD with matching separators and a valid calendar date, including leap years. |
| `subtotal`, `tax`, `total` | Nonnegative integer won, without commas, decimal points or automatic OCR repair. Supply amount + tax must equal total, tolerance **0 won**. |
| `tax` | 10% of supply amount, rounded to the nearest won with **ROUND_HALF_UP** (0.5 rounds up), tolerance **0 won**. Integer implementation: `(subtotal + 5) // 10`. |
| `item.<index>.amount` | At least one item required; nonnegative integer won; sum must equal supply amount, tolerance **0 won**. |

This profile targets ordinary 10% taxable invoices. Exemptions, amended invoices with
negative amounts, and other tax treatments need separate profiles. A checksum checks
digit consistency only; it cannot establish registration or ownership.
All added documents are fabricated, without personal data. `0000000091` is a deliberately
fake checksum-only test number with an intentional `000` prefix, not a registered business.
The fixture notice explicitly records this; invalid variants are synthetic mutations.

```sh
PYTHONPATH=src python3 src/cli.py --format json --profile kr --input fixtures/korean_invoices.json
PYTHONPATH=src python3 src/cli.py --format tsv --profile kr --input fixtures/tesseract.tsv --regions fixtures/tesseract_regions.json --doc-id SYNTHETIC-TSV
```

Both commands write `out/report.md` and `out/review.csv` (override the directory with `OUT`).
The UTF-8 CSV has columns `document_id,field,value,rule,confidence`, one row per
nonrepairable structural issue or low-confidence issue, preserving the original value.
A field triggering multiple rules has multiple rows. Standard CSV quoting preserves commas,
quotes and newlines. Missing values are empty, never invented. The Korean profile offers
no automatic repairs. The CLI includes low-confidence issues so clean-but-uncertain fields
also reach a person.

## Labeled synthetic Korean comparison

The following document-level counts are calculated and printed by
`test_measured_comparison_matches_readme` during `make test`; the test also verifies this
table matches its calculation. Labels are independent `label_defective` fixture values,
not inferred from either gate. TP/FP/FN/TN mean defective flagged / clean flagged /
defective missed / clean accepted. Confidence-only flags scores **below 0.90**;
Korean structural uses the profile above without a confidence threshold.

| gate | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| confidence-only | 0 | 1 | 6 | 1 |
| Korean structural | 6 | 0 | 0 | 2 |

These counts describe planted defects, not real OCR accuracy. The original measured-run
table above remains the legacy fixture result. All runtime code uses only the Python
standard library; `make test` needs no network. CI uses Python 3 and `make test`.
