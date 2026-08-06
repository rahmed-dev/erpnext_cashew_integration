"""
Tests for the dashboard time-series blocks (f012 c002).

Covers the two things the architecture pass flagged as the likely failure
modes: the 92-day granularity switch, and budget cycles anchored on the
budget's own grid rather than on the dashboard filter.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_dashboard_series
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from cashew_integration.dashboard_series import (
    DAILY_GRANULARITY_MAX_DAYS,
    TOP_N_FLOW_NODES,
    _flow_pairs,
    _fold_flow_nodes,
    _net_worth_block,
    build_buckets,
    bucket_key_for,
    cycle_boundaries,
    resolve_granularity,
)


class TestGranularity(FrappeTestCase):
    def test_switch_is_inclusive_of_both_endpoints(self):
        # 2026-01-01 .. 2026-04-02 is exactly 92 days counting both ends.
        self.assertEqual(resolve_granularity("2026-01-01", "2026-04-02"), "daily")
        self.assertEqual(resolve_granularity("2026-01-01", "2026-04-03"), "monthly")

    def test_single_day_period_is_one_daily_bucket(self):
        self.assertEqual(resolve_granularity("2026-03-05", "2026-03-05"), "daily")
        buckets = build_buckets("2026-03-05", "2026-03-05", "daily")
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["key"], "2026-03-05")

    def test_daily_bucket_count_matches_span(self):
        buckets = build_buckets("2026-01-01", "2026-04-02", "daily")
        self.assertEqual(len(buckets), DAILY_GRANULARITY_MAX_DAYS)


class TestMonthlyBuckets(FrappeTestCase):
    def test_partial_first_and_last_months_are_clipped_to_the_period(self):
        """A period starting mid-month must not claim the earlier part of it."""
        buckets = build_buckets("2026-01-15", "2026-04-10", "monthly")
        self.assertEqual([b["key"] for b in buckets],
                         ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"])
        self.assertEqual(buckets[0]["start"], "2026-01-15")
        self.assertEqual(buckets[0]["end"], "2026-01-31")
        self.assertEqual(buckets[-1]["start"], "2026-04-01")
        self.assertEqual(buckets[-1]["end"], "2026-04-10")

    def test_february_end_is_not_hardcoded_to_30(self):
        buckets = build_buckets("2026-02-01", "2026-03-31", "monthly")
        self.assertEqual(buckets[0]["end"], "2026-02-28")

    def test_posting_dates_collapse_to_the_month_anchor(self):
        self.assertEqual(bucket_key_for("2026-02-17", "monthly"), "2026-02-01")
        self.assertEqual(bucket_key_for("2026-02-17", "daily"), "2026-02-17")


class TestBucketTimezone(FrappeTestCase):
    def test_late_night_posting_lands_in_its_local_day(self):
        """GL Entry.posting_date is already a SITE-local date.

        The bucket key must be derived from that date and never from a UTC
        re-interpretation of it — a 23:50 local posting belongs to the day it
        was posted on, not to the next one.
        """
        posting = frappe.utils.get_datetime("2026-02-17 23:50:00")
        self.assertEqual(bucket_key_for(posting, "daily"), "2026-02-17")


class TestBudgetCycles(FrappeTestCase):
    def test_weekly_budget_over_a_quarter_yields_weekly_cycles(self):
        cycles = cycle_boundaries("2026-01-05", "Weekly", 1, "2026-01-05", "2026-04-05")
        self.assertEqual(len(cycles), 13)
        self.assertEqual(cycles[0]["start"], "2026-01-05")
        self.assertEqual(cycles[0]["end"], "2026-01-11")
        self.assertEqual(cycles[1]["start"], "2026-01-12")

    def test_cycles_align_to_the_budget_anchor_not_the_filter(self):
        """A monthly budget anchored on the 10th buckets 10th-to-9th."""
        cycles = cycle_boundaries("2026-01-10", "Monthly", 1, "2026-02-01", "2026-04-01")
        starts = [c["start"] for c in cycles]
        self.assertIn("2026-01-10", starts)
        self.assertIn("2026-02-10", starts)
        self.assertEqual(cycles[0]["end"], "2026-02-09")

    def test_trailing_cycle_past_the_window_is_flagged_partial(self):
        cycles = cycle_boundaries("2026-01-01", "Monthly", 1, "2026-01-01", "2026-03-15")
        self.assertFalse(cycles[0]["partial"])
        self.assertTrue(cycles[-1]["partial"])
        self.assertEqual(cycles[-1]["start"], "2026-03-01")

    def test_period_length_multiplies_the_unit(self):
        cycles = cycle_boundaries("2026-01-01", "Monthly", 3, "2026-01-01", "2026-12-31")
        self.assertEqual(len(cycles), 4)
        self.assertEqual(cycles[1]["start"], "2026-04-01")

    def test_filter_predating_the_anchor_still_uses_the_budget_grid(self):
        cycles = cycle_boundaries("2026-06-10", "Monthly", 1, "2026-04-01", "2026-05-31")
        self.assertEqual([c["start"] for c in cycles],
                         ["2026-03-10", "2026-04-10", "2026-05-10"])

    def test_unrecognised_reoccurrence_raises_rather_than_guessing(self):
        with self.assertRaises(frappe.ValidationError):
            cycle_boundaries("2026-01-01", "Fortnightly", 1, "2026-01-01", "2026-03-01")


class TestNetWorthBlock(FrappeTestCase):
    """`_net_worth_block` is pure, so the sign convention can be pinned exactly.

    The convention is the whole point of the block: balances arrive in raw
    debit-credit form, which makes a liability NEGATIVE, and net worth is then
    the plain sum. Getting that backwards would produce a curve that rises as
    debt grows — plausible-looking and completely wrong (f012 c005).
    """

    def test_liabilities_reduce_net_worth_and_are_reported_as_owed(self):
        running = {"Cash": [1000.0, 1200.0], "Loan": [-300.0, -300.0]}
        root_types = {"Cash": "Asset", "Loan": "Liability"}
        block = _net_worth_block(running, root_types, {"Cash": 1000.0, "Loan": -300.0}, 2)

        self.assertEqual(block["assets"], [1000.0, 1200.0])
        # Negated on the way out: the tooltip says "Owed", so it must be positive.
        self.assertEqual(block["liabilities"], [300.0, 300.0])
        self.assertEqual(block["values"], [700.0, 900.0])
        self.assertTrue(block["has_liabilities"])

    def test_a_ledger_without_liabilities_says_so(self):
        """auto_settle_cash books straight to cash, so this is the normal case."""
        block = _net_worth_block({"Cash": [50.0]}, {"Cash": "Asset"}, {"Cash": 50.0}, 1)
        self.assertFalse(block["has_liabilities"])
        self.assertEqual(block["liabilities"], [0.0])

    def test_opening_is_the_balance_carried_in_not_the_first_bucket(self):
        """The header states the change over the window; reading the first
        bucket as the opening would swallow that bucket's own movement."""
        block = _net_worth_block({"Cash": [1500.0]}, {"Cash": "Asset"}, {"Cash": 1000.0}, 1)
        self.assertEqual(block["opening"], 1000.0)
        self.assertEqual(block["closing"], 1500.0)

    def test_a_negative_net_worth_is_carried_through_untouched(self):
        """Decision 7: the curve genuinely goes deeply negative. Nothing in the
        pipeline may clamp it at zero."""
        block = _net_worth_block({"Petty Cash": [-447850.0]}, {"Petty Cash": "Asset"}, {}, 1)
        self.assertEqual(block["values"], [-447850.0])
        self.assertEqual(block["closing"], -447850.0)


class TestMoneyFlowPairing(FrappeTestCase):
    """`_flow_pairs` is where the sankey decides what a link means (f012 c008).

    A GL entry does not record its counterpart, so every link in the diagram is
    derived here from the voucher's own legs. The three rules being pinned are
    the ones a reader would be misled by if they broke: which transitions may
    be drawn at all, that a refund is netted rather than drawn backwards, and
    that everything not drawn is still counted.
    """

    ROOTS = {
        "Salary": "Income",
        "Cash": "Asset",
        "Bank": "Asset",
        "Food": "Expense",
        "Loan": "Liability",
    }

    def test_a_two_legged_voucher_pairs_exactly(self):
        pairs, excluded, allocated = _flow_pairs(
            {("JE", "A"): {"Salary": -5000.0, "Bank": 5000.0}}, self.ROOTS
        )
        self.assertEqual(pairs, {("Salary", "Bank"): 5000.0})
        self.assertEqual(excluded, {"transfers": 0.0, "other": 0.0})
        self.assertEqual(allocated, 0)

    def test_a_transfer_is_excluded_not_drawn_inside_a_column(self):
        """An Asset -> Asset link would put an arrow inside one column and make
        the graph cyclic. It is reported as a figure instead."""
        pairs, excluded, _ = _flow_pairs(
            {("JE", "A"): {"Bank": -2000.0, "Cash": 2000.0}}, self.ROOTS
        )
        self.assertEqual(pairs, {})
        self.assertEqual(excluded["transfers"], 2000.0)

    def test_a_liability_leg_is_excluded_and_counted(self):
        pairs, excluded, _ = _flow_pairs(
            {("JE", "A"): {"Loan": -1000.0, "Bank": 1000.0}}, self.ROOTS
        )
        self.assertEqual(pairs, {})
        self.assertEqual(excluded["other"], 1000.0)

    def test_a_refund_is_netted_against_the_forward_link(self):
        """A refund credits the expense and debits the account — the reverse of
        a drawable link. A sankey arrow means money moved that way, so it is
        subtracted rather than drawn."""
        pairs, _excluded, _ = _flow_pairs(
            {
                ("JE", "A"): {"Cash": -900.0, "Food": 900.0},
                ("JE", "B"): {"Food": -100.0, "Cash": 100.0},
            },
            self.ROOTS,
        )
        self.assertEqual(pairs, {("Cash", "Food"): 800.0})

    def test_a_multi_legged_voucher_splits_in_proportion_and_is_flagged(self):
        pairs, _excluded, allocated = _flow_pairs(
            {("JE", "A"): {"Cash": -750.0, "Bank": -250.0, "Food": 1000.0}},
            self.ROOTS,
        )
        self.assertEqual(pairs[("Cash", "Food")], 750.0)
        self.assertEqual(pairs[("Bank", "Food")], 250.0)
        # One source per use is still an observation, not an allocation.
        self.assertEqual(allocated, 0)

        _pairs, _excluded, allocated = _flow_pairs(
            {("JE", "B"): {"Cash": -600.0, "Bank": -400.0,
                           "Food": 700.0, "Loan": 300.0}},
            self.ROOTS,
        )
        self.assertEqual(allocated, 1)

    def test_an_unbalanced_or_one_sided_voucher_contributes_nothing(self):
        pairs, excluded, _ = _flow_pairs(
            {("JE", "A"): {"Cash": 500.0}}, self.ROOTS
        )
        self.assertEqual(pairs, {})
        self.assertEqual(excluded, {"transfers": 0.0, "other": 0.0})


class TestMoneyFlowNodes(FrappeTestCase):
    """The fold has to keep node names unique across the WHOLE graph — ECharts
    keys sankey links by name, so one label in two layers silently merges into
    a single node and creates the cycle the layer rule exists to prevent."""

    def test_a_label_used_by_two_layers_is_disambiguated(self):
        labels = {"inc": "Interest", "bank": "Bank", "exp": "Interest"}
        roots = {"inc": "Income", "bank": "Asset", "exp": "Expense"}
        nodes, links = _fold_flow_nodes(
            [("inc", "bank", 100.0), ("bank", "exp", 40.0)], labels, roots
        )
        names = sorted(n["name"] for n in nodes)
        self.assertEqual(names, ["Bank", "Interest (expense)", "Interest (income)"])
        self.assertEqual(len(set(names)), 3)
        self.assertIn({"source": "Interest (income)", "target": "Bank", "value": 100.0}, links)

    def test_the_tail_of_a_layer_folds_into_that_layers_other_node(self):
        labels = {f"e{i}": f"Cat {i}" for i in range(12)}
        roots = {f"e{i}": "Expense" for i in range(12)}
        labels["bank"] = "Bank"
        roots["bank"] = "Asset"
        raw = [("bank", f"e{i}", float(100 - i)) for i in range(12)]
        nodes, _links = _fold_flow_nodes(raw, labels, roots)
        expense_names = {n["name"] for n in nodes if n["layer"] == "Expense"}
        self.assertIn("(Other categories)", expense_names)
        self.assertEqual(len(expense_names), TOP_N_FLOW_NODES + 1)

    def test_a_middle_node_reports_throughput_not_a_balance(self):
        """In plus out. The tooltip labels it as such; the key name must not
        invite it being read as the account's balance."""
        nodes, _links = _fold_flow_nodes(
            [("inc", "bank", 100.0), ("bank", "exp", 60.0)],
            {"inc": "Salary", "bank": "Bank", "exp": "Food"},
            {"inc": "Income", "bank": "Asset", "exp": "Expense"},
        )
        bank = next(n for n in nodes if n["name"] == "Bank")
        self.assertEqual(bank["throughput"], 160.0)
