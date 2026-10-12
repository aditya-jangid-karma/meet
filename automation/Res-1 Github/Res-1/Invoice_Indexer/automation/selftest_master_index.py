"""Offline tests for master_index.py. No network, no files. Run:
  python automation\\selftest_master_index.py
"""
import unittest

from vendor_lookup import Lookup, Match
from master_index import build_index, extra_for_confident_match, value_to_type


ROWS = [
    {"Vendor Name": "Ferguson Facility Supply", "ERP Vendor ID": "V123"},
    {"Vendor Name": "Illustratus", "ERP Vendor ID": ""},   # blank code
]


class BuildIndex(unittest.TestCase):
    def test_maps_normalised_name_to_value(self):
        idx = build_index(ROWS, "Vendor Name", "ERP Vendor ID")
        self.assertEqual(idx["ferguson facility supply"], "V123")

    def test_blank_value_kept_as_empty_string(self):
        idx = build_index(ROWS, "Vendor Name", "ERP Vendor ID")
        self.assertEqual(idx["illustratus"], "")

    def test_missing_value_column_is_empty_string(self):
        idx = build_index([{"Vendor Name": "X"}], "Vendor Name", "ERP Vendor ID")
        self.assertEqual(idx["x"], "")

    def test_row_with_blank_name_is_skipped(self):
        idx = build_index([{"Vendor Name": "", "ERP Vendor ID": "Z"}],
                          "Vendor Name", "ERP Vendor ID")
        self.assertEqual(idx, {})


class ExtraForConfidentMatch(unittest.TestCase):
    def setUp(self):
        self.idx = build_index(ROWS, "Vendor Name", "ERP Vendor ID")

    def test_read_ok_returns_the_value(self):
        m = Match(value="Ferguson Facility Supply", status="READ_OK",
                  suggestion=None, how="exact")
        self.assertEqual(extra_for_confident_match(m, self.idx), "V123")

    def test_needs_review_returns_empty_even_if_name_known(self):
        m = Match(value="Ferguson Facility Supply", status="NEEDS_REVIEW",
                  suggestion="Ferguson Facility Supply", how="close")
        self.assertEqual(extra_for_confident_match(m, self.idx), "")

    def test_read_ok_but_name_not_in_index_returns_empty(self):
        m = Match(value="Unknown Co", status="READ_OK", suggestion=None,
                  how="exact")
        self.assertEqual(extra_for_confident_match(m, self.idx), "")


class ValueToType(unittest.TestCase):
    def setUp(self):
        self.lookup = Lookup(master_rows=ROWS)
        self.idx = build_index(ROWS, "Vendor Name", "ERP Vendor ID")

    def test_exact_match_types_the_code(self):
        self.assertEqual(
            value_to_type("  FERGUSON  Facility Supply ", self.lookup, self.idx),
            "V123")

    def test_close_match_types_the_name_not_a_code(self):
        # one letter dropped -> NEEDS_REVIEW -> must fall back to the raw name
        raw = "Ferguson Facilty Supply"
        self.assertEqual(value_to_type(raw, self.lookup, self.idx), raw)

    def test_unknown_name_types_the_name(self):
        raw = "Totally Unknown Vendor LLC"
        self.assertEqual(value_to_type(raw, self.lookup, self.idx), raw)

    def test_confident_match_with_blank_code_falls_back_to_name(self):
        raw = "Illustratus"          # exact match, but its code is blank
        self.assertEqual(value_to_type(raw, self.lookup, self.idx), raw)


if __name__ == "__main__":
    unittest.main()
