"""
Offline tests for the script's decision-making.

No browser opens. Nothing connects to Bottomline. No spreadsheet is read.
These test only the pure logic, from both halves of the script:

  queue_navigator.py -- how two image names are compared, how the page index
                        is built, how duplicates are spotted, and the order of
                        routes back to the queue.
  fill_plan.py       -- which integration package is tried first, what a
                        property dropdown's match count means, and the order
                        the invoice's own boxes are filled in.

Run:  python automation\\selftest_queue.py
"""

import unittest

from fill_plan import (
    DEFAULT_ORDER,
    detail_fields,
    is_known_package,
    package_candidates,
    package_verdict,
    property_candidates_for_package,
)
from master_index import build_index
from vendor_lookup import Lookup
from queue_navigator import (
    _queue_screen_signals,
    _try_menu_click,
    build_queue_index,
    image_name_from_header,
    normalise_name,
    return_routes,
    return_to_queue,
    total_pages_from_toolbar,
)


class NameMatching(unittest.TestCase):

    def test_identical_names_match(self):
        self.assertEqual(normalise_name("skm_c250i26080508080"),
                         normalise_name("skm_c250i26080508080"))

    def test_case_is_ignored(self):
        # Excel and operators are inconsistent about case. Two genuinely
        # different images in one queue differing ONLY by case is implausible,
        # and if it ever happened the duplicate check would stop the run.
        self.assertEqual(normalise_name("SKM_C250I26080508080"),
                         normalise_name("skm_c250i26080508080"))

    def test_surrounding_spaces_are_ignored(self):
        self.assertEqual(normalise_name("  washington court 12  "),
                         normalise_name("washington court 12"))

    def test_repeated_inner_spaces_collapse(self):
        self.assertEqual(normalise_name("washington   court"),
                         normalise_name("washington court"))

    def test_trailing_pdf_is_ignored(self):
        # The queue shows names without an extension, but operators often paste
        # the filename with one. Either form must find the invoice.
        self.assertEqual(normalise_name("invoice_881.pdf"),
                         normalise_name("invoice_881"))

    def test_different_names_do_not_match(self):
        self.assertNotEqual(normalise_name("invoice_881"),
                            normalise_name("invoice_882"))

    def test_empty_stays_empty(self):
        self.assertEqual(normalise_name("   "), "")
        self.assertEqual(normalise_name(None), "")


class HeaderReading(unittest.TestCase):

    def test_reads_the_name_out_of_the_header(self):
        self.assertEqual(
            image_name_from_header("Image Index - skm_c250i26080508080"),
            "skm_c250i26080508080")

    def test_tolerates_extra_spacing(self):
        self.assertEqual(
            image_name_from_header("  Image Index -   invoice_881  "),
            "invoice_881")

    def test_name_containing_a_dash_survives(self):
        self.assertEqual(
            image_name_from_header("Image Index - washington - court - 12"),
            "washington - court - 12")

    def test_wrong_screen_returns_none(self):
        # This is what proves the indexing screen actually opened.
        self.assertIsNone(image_name_from_header("Images to be Indexed"))
        self.assertIsNone(image_name_from_header(""))
        self.assertIsNone(image_name_from_header(None))


class QueueIndex(unittest.TestCase):

    def test_builds_a_name_to_page_lookup(self):
        index, duplicates = build_queue_index([
            ("invoice_881", 1),
            ("invoice_882", 1),
            ("invoice_883", 2),
        ])
        self.assertEqual(index[normalise_name("invoice_883")], 2)
        self.assertEqual(duplicates, [])

    def test_lookup_is_case_insensitive(self):
        index, _ = build_queue_index([("SKM_881", 3)])
        self.assertEqual(index[normalise_name("skm_881")], 3)

    def test_duplicates_are_reported(self):
        # The same document twice in an indexing queue usually means something
        # upstream went wrong. Guessing which one to take is exactly the kind
        # of silent choice this project refuses to make.
        index, duplicates = build_queue_index([
            ("invoice_881", 1),
            ("invoice_881", 4),
        ])
        self.assertEqual(duplicates, [normalise_name("invoice_881")])

    def test_blank_rows_are_ignored_not_indexed(self):
        index, duplicates = build_queue_index([("", 1), ("   ", 1)])
        self.assertEqual(index, {})
        self.assertEqual(duplicates, [])


class PagingToolbar(unittest.TestCase):
    """How many pages the queue says it has.

    Wrong answers here are expensive in both directions: too low and invoices
    on the unread pages are declared missing, too high and the script walks
    past the end of the queue. So "cannot tell" must stay distinguishable from
    a number -- it is the signal to fall back to watching the Next button.
    """

    def test_reads_the_count_the_operator_sees(self):
        self.assertEqual(total_pages_from_toolbar("Page 1 of 17"), 17)

    def test_reads_it_with_the_page_box_empty(self):
        # The page number lives in an <input>, and an input's value is not part
        # of the toolbar's text -- so this is the shape actually seen live.
        self.assertEqual(total_pages_from_toolbar("Page  of 17"), 17)

    def test_ignores_the_row_count_beside_it(self):
        # THE trap. The same toolbar carries "Displaying 1 - 25 of 417".
        # Matching a bare "of <number>" would read 417 pages off a 17-page
        # queue and walk 400 pages that do not exist.
        self.assertEqual(
            total_pages_from_toolbar("Page  of 17    Displaying 1 - 25 of 417"),
            17)

    def test_row_count_alone_is_not_a_page_count(self):
        self.assertIsNone(total_pages_from_toolbar("Displaying 1 - 25 of 417"))

    def test_thousands_separator_survives(self):
        self.assertEqual(total_pages_from_toolbar("Page  of 1,234"), 1234)

    def test_extra_spacing_and_case_do_not_matter(self):
        self.assertEqual(total_pages_from_toolbar("  PAGE   1   OF   9  "), 9)

    def test_unreadable_toolbar_says_so_rather_than_guessing(self):
        self.assertIsNone(total_pages_from_toolbar(""))
        self.assertIsNone(total_pages_from_toolbar(None))
        self.assertIsNone(total_pages_from_toolbar("Images to be Indexed"))

    def test_zero_pages_is_treated_as_unreadable(self):
        # "Page of 0" is not a queue this script should try to walk.
        self.assertIsNone(total_pages_from_toolbar("Page  of 0"))


class ReturnToQueueRouteOrder(unittest.TestCase):
    """The order return_to_queue() tries its routes back to the queue in.

    This is the fix for the bug where Convert to Invoice's second screen
    killed the whole run: one failed menu click used to be fatal. These
    tests only check the ORDER of routes, kept as a pure function
    (return_routes) precisely so this can be proved right without a browser
    or a live Bottomline session -- the browser-driving half is proved by
    the first live run instead, same as the rest of this file's untested
    half.
    """

    def test_menu_is_tried_first(self):
        # The menu click is the original, still-preferred route -- it works
        # from the ordinary queue screen, which is where most rows leave off.
        self.assertEqual(return_routes(has_queue_url=True)[0], "menu")
        self.assertEqual(return_routes(has_queue_url=False)[0], "menu")

    def test_queue_url_only_appears_when_one_was_captured(self):
        # No address was captured this run (page.url couldn't be read, say)
        # -- the ladder must not invent a rung that doesn't exist.
        self.assertNotIn("queue_url", return_routes(has_queue_url=False))
        self.assertIn("queue_url", return_routes(has_queue_url=True))

    def test_a_second_menu_click_is_always_the_last_resort(self):
        # Covers the case this bug actually was: the first click was simply
        # too early for the second screen to be ready. One more try, after
        # the address rung, catches that without giving up on the menu
        # entirely.
        self.assertEqual(return_routes(has_queue_url=True)[-1], "menu")
        self.assertEqual(return_routes(has_queue_url=False)[-1], "menu")

    def test_full_ladder_with_an_address_captured(self):
        self.assertEqual(return_routes(has_queue_url=True), ["menu", "queue_url", "menu"])

    def test_full_ladder_without_an_address_captured(self):
        self.assertEqual(return_routes(has_queue_url=False), ["menu", "menu"])


class QueueScreenLooksRight(unittest.TestCase):
    """Does the screen in front of us look like the indexing queue?

    Used after every attempt to get back to it -- a click or a page.goto()
    that "succeeded" and still landed nowhere near the queue must count as a
    failure, not a success. Split into a pure function (_queue_screen_signals)
    from what actually reads the two landmarks off the page, so the decision
    itself can be tested without a browser.
    """

    def test_both_landmarks_present_is_the_queue(self):
        self.assertTrue(_queue_screen_signals(True, True))

    def test_either_landmark_alone_is_enough(self):
        # The grid can be genuinely empty (a cleared queue) while the
        # page-number box still sits on the toolbar, and the reverse can be
        # true for a moment during a redraw. Neither should be read as
        # "not the queue" on its own.
        self.assertTrue(_queue_screen_signals(True, False))
        self.assertTrue(_queue_screen_signals(False, True))

    def test_neither_landmark_present_is_not_the_queue(self):
        self.assertFalse(_queue_screen_signals(False, False))


class NavigationNeverRaises(unittest.TestCase):
    """No way back to the queue may ever throw an exception at the run.

    This is the regression guard for the 2026-08-14 live failure. The menu
    item was found, the click raised inside Playwright, and the exception flew
    straight out of return_to_queue(), past the operator prompt that exists to
    handle exactly this, and killed a run with row 1 already filled and two
    invoices still to do.

    Finding a menu item is not the same as being able to click it. After
    Convert to Invoice it can be present but covered, still animating, or
    detached the moment it is reached -- Playwright raises in all three cases.
    So "it failed" must always come back as False, never as an exception.
    """

    class _AngryThing:
        """Stands in for an element that is there but refuses to co-operate."""

        def __init__(self, raise_on_count=False):
            self.raise_on_count = raise_on_count

        def count(self):
            if self.raise_on_count:
                raise RuntimeError("element detached while being counted")
            return 1

        def click(self):
            raise RuntimeError("element is covered by another element")

    class _AngryPage:
        def __init__(self, thing):
            self.thing = thing

        def locator(self, selector):
            return self

        @property
        def first(self):
            return self.thing

        def count(self):
            return self.thing.count()

        def click(self):
            return self.thing.click()

        def wait_for_timeout(self, milliseconds):
            return None

    SELECTORS = {"queue": {"menu_item": "a.x-menu-item-link",
                           "menu_item_text": "Images to be Indexed",
                           "grid_row": "tr.x-grid-row",
                           "page_number_box": "input[name=\"inputItem\"]"}}

    def test_a_click_that_raises_is_reported_as_failure(self):
        page = self._AngryPage(self._AngryThing())
        self.assertFalse(_try_menu_click(page, self.SELECTORS, lambda text: None))

    def test_a_count_that_raises_is_reported_as_failure(self):
        page = self._AngryPage(self._AngryThing(raise_on_count=True))
        self.assertFalse(_try_menu_click(page, self.SELECTORS, lambda text: None))

    def test_return_to_queue_gives_up_quietly_instead_of_exploding(self):
        # Every route fails. The caller must get a plain False so it can hand
        # the browser to the operator -- the run does not end here.
        page = self._AngryPage(self._AngryThing())
        self.assertFalse(
            return_to_queue(page, self.SELECTORS, lambda text: None,
                            queue_url="https://example.invalid/queue"))


class WhichPackageToTryFirst(unittest.TestCase):
    """The order integration packages are tried in.

    This decides which accounting system an invoice is offered up to first, so
    it is worth being fussy about. The spreadsheet's own value leads when it is
    one we recognise; anything else falls back to a fixed order rather than
    being typed into Bottomline on trust.
    """

    def test_the_sheets_own_value_is_tried_first(self):
        self.assertEqual(package_candidates("INTACCT")[0], "INTACCT")
        self.assertEqual(package_candidates("YARDI")[0], "YARDI")

    def test_the_other_package_is_still_tried_second(self):
        # "Not under the first one" must always be followed by actually
        # checking the other -- otherwise the search is not a search.
        self.assertEqual(package_candidates("INTACCT"), ["INTACCT", "YARDI"])
        self.assertEqual(package_candidates("YARDI"), ["YARDI", "INTACCT"])

    def test_case_and_stray_spaces_are_forgiven(self):
        # Excel cells collect trailing spaces and operators are inconsistent
        # about capitals. Neither should change which system an invoice lands in.
        self.assertEqual(package_candidates(" intacct ")[0], "INTACCT")
        self.assertEqual(package_candidates("Yardi")[0], "YARDI")

    def test_a_blank_cell_falls_back_to_the_fixed_order(self):
        self.assertEqual(package_candidates(""), list(DEFAULT_ORDER))
        self.assertEqual(package_candidates(None), list(DEFAULT_ORDER))

    def test_an_unrecognised_package_is_never_passed_through(self):
        # THE important one. A typo like "YARDI2", or a package that was
        # retired, must not be typed into a live accounting system just
        # because somebody put it in a cell.
        self.assertEqual(package_candidates("YARDI2"), list(DEFAULT_ORDER))
        self.assertEqual(package_candidates("Sage"), list(DEFAULT_ORDER))
        self.assertNotIn("Sage", package_candidates("Sage"))

    def test_known_packages_are_recognised(self):
        self.assertTrue(is_known_package("yardi"))
        self.assertTrue(is_known_package("INTACCT"))
        self.assertFalse(is_known_package("Sage"))
        self.assertFalse(is_known_package(""))


class WhatThePropertyDropdownMeans(unittest.TestCase):
    """Reading a property dropdown as a verdict on the package on screen.

    A property only appears if it belongs to the integration package currently
    selected, so the count of matches IS the test result.
    """

    def test_one_match_confirms_the_package(self):
        self.assertEqual(package_verdict(1), "confirmed")

    def test_several_matches_still_confirm_it(self):
        # The property is plainly under this package -- there are just too many
        # to choose between, which is the operator's job, not the script's.
        self.assertEqual(package_verdict(2), "ambiguous")
        self.assertEqual(package_verdict(9), "ambiguous")

    def test_no_match_means_try_the_other_package(self):
        self.assertEqual(package_verdict(0), "not_here")


class OrderTheInvoiceBoxesAreFilled(unittest.TestCase):
    """Phase C: the invoice's own details, after the package and vendor."""

    def test_the_expected_order(self):
        keys = ["vendor", "property", "invoice_number", "invoice_date",
                "invoice_due_date", "amount", "integration_package"]
        self.assertEqual(
            detail_fields(keys),
            ["invoice_number", "invoice_date", "invoice_due_date", "amount"])

    def test_package_property_and_vendor_are_not_repeated(self):
        # They were handled in Phases A and B. Typing them again would undo a
        # dropdown selection that has already been made and verified.
        filled = detail_fields(["vendor", "property", "integration_package",
                                "amount"])
        self.assertNotIn("vendor", filled)
        self.assertNotIn("property", filled)
        self.assertNotIn("integration_package", filled)

    def test_a_newly_added_column_is_still_filled(self):
        # If someone adds a box to selectors.json and forgets this file, the
        # new box must still get typed. A silently missing value on an invoice
        # is far harder to spot than one filled in an odd order.
        filled = detail_fields(["amount", "purchase_order"])
        self.assertIn("purchase_order", filled)

    def test_missing_boxes_are_simply_absent(self):
        self.assertEqual(detail_fields(["amount"]), ["amount"])
        self.assertEqual(detail_fields([]), [])


class PropertyCandidatesForPackage(unittest.TestCase):
    ROWS = [{"Property Name": "Fairfax Court Apts", "Property Code": "414-460"},
            {"Property Name": "Oakwood", "Property Code": ""}]

    def setUp(self):
        self.lookup = Lookup(master_rows=self.ROWS, name_col="Property Name")
        self.index = build_index(self.ROWS, "Property Name", "Property Code")

    def test_yardi_confident_match_with_code_tries_code_then_name(self):
        candidates = property_candidates_for_package(
            "YARDI", "Fairfax Court Apts", self.lookup, self.index)
        self.assertEqual(candidates, ["414-460", "Fairfax Court Apts"])

    def test_yardi_confident_match_blank_code_tries_name_only(self):
        candidates = property_candidates_for_package(
            "YARDI", "Oakwood", self.lookup, self.index)
        self.assertEqual(candidates, ["Oakwood"])

    def test_yardi_uncertain_name_tries_name_only_never_a_guessed_code(self):
        # one letter dropped -- a close, not exact, match
        candidates = property_candidates_for_package(
            "YARDI", "Fairfax Court Apt", self.lookup, self.index)
        self.assertEqual(candidates, ["Fairfax Court Apt"])

    def test_intacct_never_uses_a_code_even_if_one_exists(self):
        candidates = property_candidates_for_package(
            "INTACCT", "Fairfax Court Apts", self.lookup, self.index)
        self.assertEqual(candidates, ["Fairfax Court Apts"])

    def test_no_lookup_falls_back_to_name_only(self):
        candidates = property_candidates_for_package(
            "YARDI", "Anything", None, {})
        self.assertEqual(candidates, ["Anything"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
