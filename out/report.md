# OCR field gate

8 documents.

## Repairable — the arithmetic confirms the repair

- `INV-1005` `subtotal` — 'l500.00' is not a number; letters here are confused with digits. Suggested: `1500.00` (confidence was 0.99)

## Needs a person

- `INV-1002` `total` **arithmetic** — subtotal 800.0 + tax 160.0 = 960.0, document says 860.0 (confidence 0.97)
- `INV-1004` `date` **impossible_date** — month 13, day 2 (confidence 0.94)
- `INV-1006` `vendor` **missing** — required field is empty (confidence 0.40)
- `INV-1007` `invoice_no` **duplicate** — already used by INV-1002 (confidence 0.98)