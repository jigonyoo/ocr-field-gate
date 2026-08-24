# ocr-field-gate

**Confidence is not accuracy.** A recognition engine reports how sure it is about the *shapes* it
saw, not whether the *value* is right. This gate checks the structure instead — arithmetic, format,
character class, uniqueness — and uses confidence as one more signal, never as the decision.

```
make demo    # runs both gates over the same batch
make test    # 11 tests
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
tests/                   11 tests - 6 assert that confidence misses what structure catches
```
