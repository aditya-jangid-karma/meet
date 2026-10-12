"""Offline tests for harvest_aliases.py.

No network, no git, and never touches the real masters\\aliases.csv or a real
invoices.xlsx -- every test builds its own tiny in-memory workbook (openpyxl)
and writes to a TEMP aliases file (tempfile), which is removed afterwards.

Run:  python automation\\selftest_harvest.py
"""
import csv
import os
import shutil
import tempfile
import unittest

from openpyxl import Workbook

from harvest_aliases import harvest, _key

HEADERS = ["Image Name", "Vendor", "Property", "Invoice Number",
           "Invoice Date", "Invoice Due Date", "Amount",
           "Qwen Vendor (raw)", "Qwen Status"]

MASTER_ROWS = [
    {"Vendor Name": "Ferguson Facility Supply",
     "Address": "123 Main St, Lenexa, KS 66214"},
    {"Vendor Name": "Illustratus", "Address": "8455 Lenexa Drive"},
]


def _cols():
    return {_key(h): i for i, h in enumerate(HEADERS)}


def _make_xlsx(path, data_rows):
    """Build a tiny Invoices sheet. `data_rows` is a list of dicts keyed by
    the same normalised keys _key() would produce (e.g. "vendor",
    "qwen_vendor_raw"); any header not given for a row is left blank."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    ws.append(HEADERS)
    cols = _cols()
    for data in data_rows:
        row = [""] * len(HEADERS)
        for key, value in data.items():
            row[cols[key]] = value
        ws.append(row)
    wb.save(path)


class HarvestTempCase(unittest.TestCase):
    """Common setup: a scratch folder holding the temp xlsx + temp aliases
    file for one test, cleaned up afterwards. Never touches the real
    masters\\aliases.csv."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="harvest_selftest_")
        self.xlsx_path = os.path.join(self.tmpdir, "invoices.xlsx")
        self.aliases_path = os.path.join(self.tmpdir, "aliases.csv")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _read_aliases(self):
        if not os.path.exists(self.aliases_path):
            return []
        with open(self.aliases_path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))


class KnownVendorCorrection(HarvestTempCase):
    def test_correction_to_known_vendor_produces_alias(self):
        _make_xlsx(self.xlsx_path, [
            {"vendor": "Ferguson Facility Supply",
             "qwen_vendor_raw": "Fergusen Facility"},
        ])
        summary = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                          apply=True)

        self.assertEqual(summary["corrections_found"], 1)
        self.assertEqual(summary["aliases_added"], 1)
        self.assertEqual(summary["aliases_refreshed"], 0)
        self.assertEqual(summary["new_vendors"], [])
        self.assertTrue(summary["applied"])

        rows = self._read_aliases()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw"], "Fergusen Facility")
        self.assertEqual(rows[0]["correct"], "Ferguson Facility Supply")
        self.assertEqual(rows[0]["count"], "1")
        self.assertTrue(rows[0]["last_seen"])  # today's date, non-blank


class UnknownVendorCorrection(HarvestTempCase):
    def test_correction_to_unknown_vendor_reported_not_aliased(self):
        _make_xlsx(self.xlsx_path, [
            {"vendor": "Brand New Plumbing LLC",
             "qwen_vendor_raw": "Brnad New Plumbing"},
        ])
        summary = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                          apply=True)

        self.assertEqual(summary["corrections_found"], 1)
        self.assertEqual(summary["aliases_added"], 0)
        self.assertEqual(summary["aliases_refreshed"], 0)
        self.assertEqual(summary["new_vendors"], ["Brand New Plumbing LLC"])

        # No alias file should have been created/written for this vendor.
        rows = self._read_aliases()
        self.assertEqual(rows, [])


class NoCorrection(HarvestTempCase):
    def test_no_correction_when_vendor_matches_raw_ignoring_case_space(self):
        _make_xlsx(self.xlsx_path, [
            {"vendor": "  FERGUSON Facility Supply ",
             "qwen_vendor_raw": "Ferguson Facility Supply"},
        ])
        summary = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                          apply=True)

        self.assertEqual(summary["corrections_found"], 0)
        self.assertEqual(summary["aliases_added"], 0)
        self.assertEqual(summary["aliases_refreshed"], 0)
        self.assertEqual(summary["new_vendors"], [])
        self.assertEqual(self._read_aliases(), [])

    def test_blank_raw_or_corrected_produces_nothing(self):
        _make_xlsx(self.xlsx_path, [
            {"vendor": "Ferguson Facility Supply", "qwen_vendor_raw": ""},
            {"vendor": "", "qwen_vendor_raw": "Fergusen Facility"},
        ])
        summary = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                          apply=True)
        self.assertEqual(summary["corrections_found"], 0)
        self.assertEqual(self._read_aliases(), [])


class Idempotency(HarvestTempCase):
    def test_running_twice_bumps_count_not_duplicate_rows(self):
        _make_xlsx(self.xlsx_path, [
            {"vendor": "Ferguson Facility Supply",
             "qwen_vendor_raw": "Fergusen Facility"},
        ])
        first = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                        apply=True)
        self.assertEqual(first["aliases_added"], 1)
        self.assertEqual(first["aliases_refreshed"], 0)

        second = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                         apply=True)
        self.assertEqual(second["aliases_added"], 0)
        self.assertEqual(second["aliases_refreshed"], 1)

        rows = self._read_aliases()
        self.assertEqual(len(rows), 1)          # still just one row
        self.assertEqual(rows[0]["count"], "2")  # bumped, not duplicated


class PreviewMode(HarvestTempCase):
    def test_preview_mode_writes_nothing(self):
        _make_xlsx(self.xlsx_path, [
            {"vendor": "Ferguson Facility Supply",
             "qwen_vendor_raw": "Fergusen Facility"},
        ])
        summary = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                          apply=False)

        self.assertEqual(summary["aliases_added"], 1)  # would-add, reported
        self.assertFalse(summary["applied"])
        # Crucially, nothing was actually written to disk.
        self.assertFalse(os.path.exists(self.aliases_path))

    def test_preview_then_apply_are_consistent(self):
        _make_xlsx(self.xlsx_path, [
            {"vendor": "Ferguson Facility Supply",
             "qwen_vendor_raw": "Fergusen Facility"},
        ])
        preview = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                          apply=False)
        self.assertFalse(os.path.exists(self.aliases_path))

        applied = harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS,
                          apply=True)
        self.assertEqual(preview["aliases_added"], applied["aliases_added"])
        self.assertTrue(os.path.exists(self.aliases_path))


class ExistingAliasFilePreserved(HarvestTempCase):
    def test_existing_unrelated_alias_row_is_preserved(self):
        with open(self.aliases_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["raw", "correct", "count", "last_seen"])
            writer.writeheader()
            writer.writerow({"raw": "Someone Else Co", "correct": "Illustratus",
                             "count": "3", "last_seen": "2026-01-01"})

        _make_xlsx(self.xlsx_path, [
            {"vendor": "Ferguson Facility Supply",
             "qwen_vendor_raw": "Fergusen Facility"},
        ])
        harvest(self.xlsx_path, self.aliases_path, MASTER_ROWS, apply=True)

        rows = self._read_aliases()
        self.assertEqual(len(rows), 2)
        raws = {r["raw"] for r in rows}
        self.assertEqual(raws, {"Someone Else Co", "Fergusen Facility"})
        # The pre-existing row is untouched.
        pre_existing = next(r for r in rows if r["raw"] == "Someone Else Co")
        self.assertEqual(pre_existing["count"], "3")
        self.assertEqual(pre_existing["last_seen"], "2026-01-01")


class PropertyHarvest(HarvestTempCase):
    PROP_MASTER = [{"Property Name": "Heather Hill", "Address": ""},
                   {"Property Name": "Oakwood", "Address": ""}]

    def _make_property_xlsx(self, data_rows):
        from openpyxl import Workbook
        headers = ["Image Name", "Vendor", "Property",
                   "Qwen Property (raw)", "Property Status"]
        wb = Workbook()
        ws = wb.active
        ws.title = "Invoices"
        ws.append(headers)
        cols = {_key(h): i for i, h in enumerate(headers)}
        for data in data_rows:
            row = [""] * len(headers)
            for key, value in data.items():
                row[cols[key]] = value
            ws.append(row)
        wb.save(self.xlsx_path)

    def test_correction_to_known_property_produces_alias(self):
        self._make_property_xlsx([
            {"property": "Heather Hill", "qwen_property_raw": "Heathr Hil"},
        ])
        summary = harvest(self.xlsx_path, self.aliases_path, self.PROP_MASTER,
                          apply=True, name_col="Property Name",
                          corrected_key="property", raw_key="qwen_property_raw")
        self.assertEqual(summary["aliases_added"], 1)
        rows = self._read_aliases()
        self.assertEqual(rows[0]["raw"], "Heathr Hil")
        self.assertEqual(rows[0]["correct"], "Heather Hill")

    def test_correction_to_unknown_property_is_not_aliased(self):
        self._make_property_xlsx([
            {"property": "Brand New Place", "qwen_property_raw": "Brnd New Plc"},
        ])
        summary = harvest(self.xlsx_path, self.aliases_path, self.PROP_MASTER,
                          apply=True, name_col="Property Name",
                          corrected_key="property", raw_key="qwen_property_raw")
        self.assertEqual(summary["aliases_added"], 0)
        self.assertEqual(summary["new_vendors"], ["Brand New Place"])
        self.assertEqual(self._read_aliases(), [])   # guarantee A holds


if __name__ == "__main__":
    unittest.main()
