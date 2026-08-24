import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import gate

FX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "invoices.json")
DOCS = gate.load(FX)
S = gate.check(DOCS)
C = gate.confidence_only(DOCS)

def of(doc=None, rule=None):
    return [i for i in S if (doc is None or i.doc == doc) and (rule is None or i.rule == rule)]

class ConfidenceIsNotAccuracy(unittest.TestCase):
    """The whole reason this repo exists. Each of these was reported by the engine with
    high confidence and is wrong anyway."""

    def test_the_highest_confidence_field_in_the_batch_is_wrong(self):
        worst = max((f["conf"], d["doc"], k) for d in DOCS for k, f in d["fields"].items()
                    if f["text"] and not f["text"].replace(".", "").isdigit()
                    and k in gate.NUMERIC_FIELDS)
        self.assertEqual(worst[1], "INV-1005")
        self.assertGreaterEqual(worst[0], 0.99)
        self.assertTrue(of("INV-1005", "confused_character"))

    def test_arithmetic_error_carries_high_confidence(self):
        i = of("INV-1002", "arithmetic")[0]
        self.assertGreater(i.conf, gate.CONF_FLOOR)

    def test_impossible_date_carries_high_confidence(self):
        i = of("INV-1004", "impossible_date")[0]
        self.assertGreater(i.conf, gate.CONF_FLOOR)

    def test_duplicate_invoice_number_carries_high_confidence(self):
        i = of("INV-1007", "duplicate")[0]
        self.assertGreater(i.conf, gate.CONF_FLOOR)

    def test_confidence_gate_misses_every_one_of_them(self):
        seen = {i.doc for i in C}
        for d in ("INV-1002", "INV-1004", "INV-1005", "INV-1007"):
            self.assertNotIn(d, seen, f"{d} should be invisible to a confidence threshold")

    def test_confidence_gate_flags_a_document_that_is_structurally_fine(self):
        self.assertIn("INV-1003", {i.doc for i in C})
        self.assertFalse([i for i in of("INV-1003") if i.rule != "confused_character"])

class ItRepairsOnlyWhatEvidenceSupports(unittest.TestCase):
    def test_the_only_repairable_issue_is_confirmed_by_arithmetic(self):
        rep = [i for i in S if i.repairable]
        self.assertEqual(len(rep), 1)
        self.assertEqual(rep[0].suggestion, "1500.00")
        d = [x for x in DOCS if x["doc"] == "INV-1005"][0]
        sub, tax, tot = 1500.00, float(d["fields"]["tax"]["text"]), float(d["fields"]["total"]["text"])
        self.assertEqual(round(sub + tax, 2), tot)

    def test_nothing_else_is_marked_repairable(self):
        for i in S:
            if i.rule in ("arithmetic", "impossible_date", "duplicate", "missing"):
                self.assertFalse(i.repairable, f"{i.rule} must not be auto-repaired")

    def test_missing_field_is_reported_not_filled(self):
        m = of("INV-1006", "missing")
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0].fld, "vendor")
        self.assertFalse(m[0].suggestion)

class ItDoesNotOverreach(unittest.TestCase):
    def test_clean_documents_produce_nothing(self):
        for d in ("INV-1001", "INV-1008"):
            self.assertFalse(of(d), f"{d} is clean and should not be flagged")

    def test_every_issue_names_a_field_and_a_rule(self):
        for i in S:
            self.assertTrue(i.fld and i.rule and i.detail)

if __name__ == "__main__":
    unittest.main()
