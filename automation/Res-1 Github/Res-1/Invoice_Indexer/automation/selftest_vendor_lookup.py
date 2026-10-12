"""Offline tests for vendor_lookup.py.

No network. The only real file touched is masters\\vendors.csv, and only to
read it (never written to). Every other test uses small, made-up master
lists kept in memory so the logic can be checked in isolation.

Run:  python automation\\selftest_vendor_lookup.py
"""
import csv
import os
import tempfile
import unittest

from vendor_lookup import (_normalise, load_master, load_aliases,
                           load_alias_examples, Lookup)


VENDORS_CSV = os.path.join(os.path.dirname(__file__), "..", "masters",
                            "vendors.csv")


class AliasHit(unittest.TestCase):
    def test_alias_returns_correction_read_ok(self):
        aliases = {_normalise("Fergusen Facility"): "Ferguson Facility Supply"}
        lookup = Lookup(master_rows=[], aliases=aliases)
        result = lookup.match("Fergusen Facility")
        self.assertEqual(result.value, "Ferguson Facility Supply")
        self.assertEqual(result.status, "READ_OK")
        self.assertEqual(result.how, "alias")
        self.assertIsNone(result.suggestion)


class ExactHit(unittest.TestCase):
    def test_exact_master_hit_uses_canonical_spelling(self):
        # Real name, straight from masters\vendors.csv.
        rows = load_master(VENDORS_CSV)
        canonical = rows[0]["Vendor Name"]  # "Illustratus"
        self.assertTrue(canonical)

        lookup = Lookup(master_rows=rows)
        # Feed it a case/space-mangled version of the same name.
        mangled = "  " + canonical.upper() + "  "
        result = lookup.match(mangled)
        self.assertEqual(result.value, canonical)
        self.assertEqual(result.status, "READ_OK")
        self.assertEqual(result.how, "exact")
        self.assertIsNone(result.suggestion)


class CloseMatch(unittest.TestCase):
    def test_close_but_not_exact_flags_for_review_keeps_raw(self):
        rows = [{"Vendor Name": "Ferguson Facility Supply",
                 "Address": "123 Main St, Lenexa, KS 66214"}]
        lookup = Lookup(master_rows=rows)

        raw = "Ferguson Facilty Supply"  # one letter dropped -- typo, not exact
        result = lookup.match(raw)

        self.assertEqual(result.status, "NEEDS_REVIEW")
        self.assertEqual(result.value, raw)  # RAW kept, never auto-filled
        self.assertEqual(result.how, "close")
        self.assertEqual(result.suggestion, "Ferguson Facility Supply")


class NoMatch(unittest.TestCase):
    def test_unknown_vendor_returns_raw_with_no_suggestion(self):
        rows = [{"Vendor Name": "Ferguson Facility Supply",
                 "Address": "123 Main St, Lenexa, KS 66214"}]
        lookup = Lookup(master_rows=rows)

        raw = "Completely Different Vendor LLC"
        result = lookup.match(raw)

        self.assertEqual(result.value, raw)
        self.assertEqual(result.status, "NEEDS_REVIEW")
        self.assertEqual(result.how, "none")
        self.assertIsNone(result.suggestion)


class AddressTiebreak(unittest.TestCase):
    def setUp(self):
        # Two vendors with very similar names, at different addresses. Both
        # are close enough to the raw name to clear the 0.90 bar on name
        # alone -- "Ind" is actually the CLOSER name match of the two -- so
        # this only passes if the address is what decides the winner.
        self.rows = [
            {"Vendor Name": "Sunrise Plumbing Co",
             "Address": "1 First St, Lenexa, KS 66214"},
            {"Vendor Name": "Sunrise Plumbing Ind",
             "Address": "99 Test Ave, Reno, NV 89501"},
        ]
        self.lookup = Lookup(master_rows=self.rows)
        self.raw = "Sunrise Plumbing Inc"

    def test_without_address_picks_closest_name(self):
        result = self.lookup.match(self.raw)
        self.assertEqual(result.suggestion, "Sunrise Plumbing Ind")

    def test_with_address_the_address_decides(self):
        result = self.lookup.match(
            self.raw, address="1 First St, Lenexa, KS 66214")
        self.assertEqual(result.suggestion, "Sunrise Plumbing Co")


class LoaderEdgeCases(unittest.TestCase):
    def test_load_aliases_missing_file_returns_empty_dict(self):
        self.assertEqual(load_aliases("no_such_file_anywhere.csv"), {})

    def test_load_master_missing_file_returns_empty_list(self):
        self.assertEqual(load_master("no_such_file_anywhere.csv"), [])

    def test_load_master_reads_real_vendors_csv(self):
        rows = load_master(VENDORS_CSV)
        self.assertGreater(len(rows), 0)
        self.assertIn("Vendor Name", rows[0])


class AliasExamples(unittest.TestCase):
    """Tests for load_alias_examples(). Always uses a temp CSV -- never
    touches the real masters\\aliases.csv."""

    def _write_csv(self, rows):
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", newline="", delete=False)
        writer = csv.writer(handle)
        writer.writerow(["raw", "correct", "count", "last_seen"])
        writer.writerows(rows)
        handle.close()
        return handle.name

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(
            load_alias_examples("no_such_file_anywhere.csv"), [])

    def test_sorted_by_count_desc_then_last_seen_desc_and_capped(self):
        path = self._write_csv([
            ["Fergusen", "Ferguson Facility Supply", "3", "2026-01-01"],
            ["Ace Plumbng", "Ace Plumbing Inc", "9", "2026-02-01"],
            ["Sunrise Plumb", "Sunrise Plumbing Co", "9", "2026-06-01"],
            ["Smithe Elec", "Smith Electric", "1", "2026-03-01"],
            ["Old One", "Old Vendor Corp", "1", "2026-01-15"],
            ["Blank Row Skip", "", "5", "2026-01-01"],  # blank correct -> skip
            ["", "Also Skip", "5", "2026-01-01"],       # blank raw -> skip
        ])
        try:
            result = load_alias_examples(path, limit=3)
            self.assertEqual(result, [
                ("Sunrise Plumb", "Sunrise Plumbing Co"),   # count 9, newest
                ("Ace Plumbng", "Ace Plumbing Inc"),        # count 9, older
                ("Fergusen", "Ferguson Facility Supply"),   # count 3
            ])
        finally:
            os.remove(path)

    def test_blank_or_missing_count_treated_as_zero(self):
        path = self._write_csv([
            ["Has Count", "Has Count Corp", "2", "2026-01-01"],
            ["No Count", "No Count Corp", "", "2026-01-01"],
        ])
        try:
            result = load_alias_examples(path, limit=5)
            self.assertEqual(result, [
                ("Has Count", "Has Count Corp"),
                ("No Count", "No Count Corp"),
            ])
        finally:
            os.remove(path)

    def test_raw_text_is_not_normalised(self):
        # The original (messy) raw text must be preserved -- this feeds
        # Qwen's prompt, not the lookup dict.
        path = self._write_csv([
            ["  FERGUSEN   facility ", "Ferguson Facility Supply", "1",
             "2026-01-01"],
        ])
        try:
            result = load_alias_examples(path, limit=5)
            self.assertEqual(result[0][0], "  FERGUSEN   facility ")
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
