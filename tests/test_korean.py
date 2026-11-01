import copy
import csv
import io
import json
from pathlib import Path
import sys
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import adapters
import compare
import gate
import korean_invoice as kr
import review

FIXTURE = json.loads((ROOT / "fixtures/korean_invoices.json").read_text(encoding="utf-8"))
DOCS = [adapters.from_json(d) for d in FIXTURE["documents"]]


class Adapters(unittest.TestCase):
    def test_json_preserves_values_confidence_coordinates(self):
        field = DOCS[0]["fields"]["business_no"]
        self.assertEqual(field, {"text": "0000000091", "conf": .99, "bbox": [0, 0, 150, 15]})
        self.assertIn("fake", FIXTURE["notice"])

    def test_tsv_real_columns_and_normalization(self):
        regions = json.loads((ROOT / "fixtures/tesseract_regions.json").read_text())
        regions["empty"] = [400, 400, 10, 10]
        doc = adapters.from_tesseract_tsv(
            (ROOT / "fixtures/tesseract.tsv").read_text(), "SYNTHETIC-TSV", regions)
        self.assertEqual(doc["fields"]["vendor"],
                         {"text": "SYNTHETIC ONLY", "conf": .915, "bbox": [10, 10, 80, 10]})
        self.assertEqual(doc["fields"]["empty"]["conf"], 0)
        self.assertEqual(doc["fields"]["business_no"]["text"], "0000000091")
        self.assertFalse(kr.check([doc]))

    def test_invalid_input_rejected(self):
        entry = copy.deepcopy(FIXTURE["documents"][0])
        entry["fields"].append(entry["fields"][0])
        with self.assertRaises(ValueError):
            adapters.from_json(entry)
        for confidence in (-1, 1.01, float("nan")):
            entry = copy.deepcopy(FIXTURE["documents"][0])
            entry["fields"][0]["confidence"] = confidence
            with self.assertRaises(ValueError):
                adapters.from_json(entry)
        with self.assertRaises(ValueError):
            adapters.from_tesseract_tsv("text\nhello", "x", {})

    def test_ambiguous_tsv_region_rejected(self):
        with self.assertRaises(ValueError):
            adapters.from_tesseract_tsv((ROOT / "fixtures/tesseract.tsv").read_text(), "x",
                                        {"a": [0, 0, 500, 500], "b": [0, 0, 500, 500]})


class KoreanRules(unittest.TestCase):
    def changed(self, **values):
        doc = copy.deepcopy(DOCS[0])
        for name, value in values.items():
            doc["fields"][name]["text"] = value
        return doc

    def rules(self, doc):
        return {i.rule for i in kr.check([doc])}

    def test_checksum_includes_ninth_digit_carry(self):
        self.assertTrue(kr.valid_business_number("0000000091"))
        for value in ("0000000092", "000000009", "00000000911", "000-00-0091", "００００００００９１"):
            self.assertFalse(kr.valid_business_number(value))
        # Each position's corruption must be noticed for this synthetic example.
        for index in range(10):
            value = list("0000000091")
            value[index] = str((int(value[index]) + 1) % 10)
            self.assertFalse(kr.valid_business_number("".join(value)))

    def test_vat_round_half_up_boundaries_and_zero_tolerance(self):
        for sub, tax in ((0, 0), (4, 0), (5, 1), (14, 1), (15, 2), (1005, 101)):
            doc = self.changed(subtotal=str(sub), tax=str(tax), total=str(sub + tax))
            self.assertNotIn("kr_vat", self.rules(doc))
            doc["fields"]["tax"]["text"] = str(tax + 1)
            self.assertIn("kr_vat", self.rules(doc))

    def test_dates_include_calendar_validation(self):
        for value in ("2024-02-29", "2024.02.29"):
            self.assertNotIn("kr_date", self.rules(self.changed(date=value)))
        for value in ("2026-02-29", "2026.04.31", "2026-03.14", "2026-3-14", "0000-01-01", ""):
            self.assertIn("kr_date", self.rules(self.changed(date=value)))

    def test_missing_and_malformed_amounts_are_not_silently_skipped(self):
        for value in ("", "1,005", "1005.00", "-1", "NaN", "1O05"):
            self.assertIn("kr_won", self.rules(self.changed(subtotal=value)))
        doc = copy.deepcopy(DOCS[0])
        del doc["fields"]["tax"]
        self.assertIn("kr_won", self.rules(doc))
        doc["fields"] = {k: v for k, v in doc["fields"].items() if not k.startswith("item.")}
        self.assertIn("kr_items_missing", self.rules(doc))
        self.assertIn("kr_won", self.rules(self.changed(**{"item.1.amount": "oops"})))

    def test_labeled_defects_have_expected_rules(self):
        expected = {"KR-CHECKSUM": "business_checksum", "KR-TOTAL": "kr_total",
                    "KR-VAT": "kr_vat", "KR-DATE": "kr_date",
                    "KR-ITEM": "kr_items_sum", "KR-FORMAT": "kr_date"}
        for doc in DOCS:
            rules = self.rules(doc)
            self.assertEqual(rules, {expected[doc["doc"]]} if doc["doc"] in expected else set())

    def test_csv_round_trip_and_missing_value(self):
        doc = self.changed(date='bad,"date"\nnext')
        del doc["fields"]["tax"]
        issues = kr.check([doc]) + gate.confidence_only([doc])
        stream = io.StringIO(newline="")
        review.write_csv(stream, [doc], issues)
        rows = list(csv.DictReader(io.StringIO(stream.getvalue())))
        self.assertEqual(len(rows), len(issues))
        row = next(row for row in rows if row["field"] == "date")
        self.assertEqual(row, {"document_id": doc["doc"], "field": "date",
                               "value": 'bad,"date"\nnext', "rule": "kr_date", "confidence": "0.99"})
        self.assertEqual(next(row for row in rows if row["field"] == "tax")["value"], "")

    def test_measured_comparison_matches_readme(self):
        labels = {d["id"]: d["label_defective"] for d in FIXTURE["documents"]}
        measured = compare.comparison(DOCS, labels)
        print("\nSynthetic Korean invoice measurement:\n" + measured)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(measured, readme)


class CLI(unittest.TestCase):
    def test_json_and_tsv_generate_review_queue(self):
        cases = [
            (["--format", "json", "--input", "fixtures/korean_invoices.json"], 7),
            (["--format", "tsv", "--input", "fixtures/tesseract.tsv",
              "--regions", "fixtures/tesseract_regions.json", "--doc-id", "SYNTHETIC-TSV"], 0),
        ]
        for args, count in cases:
            with self.subTest(args=args), tempfile.TemporaryDirectory(dir=ROOT) as output:
                result = subprocess.run([sys.executable, "src/cli.py", "--profile", "kr", *args],
                                        cwd=ROOT, env=dict(os.environ, OUT=output),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                with open(Path(output) / "review.csv", encoding="utf-8", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(len(rows), count)
                self.assertTrue((Path(output) / "report.md").is_file())


if __name__ == "__main__":
    unittest.main()
