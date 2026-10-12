"""Offline tests for the two new invoice_recorder.py helpers that back the
2026-09-03 Phase A changes: reading back a manually-selected package, and
(indirectly, via fill_plan) the Yardi code-first candidate order. No browser
opens -- FakePage/FakeBox below are plain duck-typed stand-ins, not real
Playwright objects, so this needs no live Bottomline and no installed browser.
Run:  python automation\\selftest_recorder_property.py
"""
import unittest

from invoice_recorder import _read_selected_package


class FakeBox:
    def __init__(self, value):
        self._value = value

    def input_value(self):
        return self._value


class FakeLocatorResult:
    def __init__(self, value):
        self.first = FakeBox(value)


class FakePage:
    def __init__(self, value):
        self._value = value

    def locator(self, selector):
        return FakeLocatorResult(self._value)


class RaisingPage:
    def locator(self, selector):
        raise RuntimeError("boom")


SELECTORS = {"fill": {"integration_package": "#pkg"}}


class ReadSelectedPackage(unittest.TestCase):
    def test_recognised_package_is_normalised_and_returned(self):
        page = FakePage(" yardi ")
        self.assertEqual(_read_selected_package(page, SELECTORS), "YARDI")

    def test_unrecognised_text_returns_none(self):
        page = FakePage("something else")
        self.assertIsNone(_read_selected_package(page, SELECTORS))

    def test_missing_selector_returns_none(self):
        self.assertIsNone(_read_selected_package(FakePage("YARDI"), {"fill": {}}))

    def test_box_raising_is_swallowed_and_returns_none(self):
        self.assertIsNone(_read_selected_package(RaisingPage(), SELECTORS))


if __name__ == "__main__":
    unittest.main()
