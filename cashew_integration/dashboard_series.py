"""Time-series blocks for the SPA Finance Dashboard (f012 c002).

Three additive blocks consumed by `api.dashboard_summary`:

    daily_spend    one scalar per calendar day, ALWAYS daily, dense (a day with
                   no expense posting is emitted as 0). Feeds the calendar
                   heatmap (c007), which needs an uninterrupted day grid.
    series         income / expense totals, per-category breakdowns and
                   per-account balance history, bucketed daily when the period
                   spans <= 92 days and monthly beyond that.
    budget_cycles  one bucket per BUDGET cycle, anchored on each budget's own
                   start_date + reoccurrence + period_length. The server is the
                   only place that knows the anchor and the enum, so the
                   bucketing happens here and never in the client.
    money_flow     the period's income, the accounts it landed in and the
                   categories it left through, as sankey nodes and links (c008).
                   Pairing accounts within a voucher needs the whole voucher,
                   which only the server has.

Every figure is derived from GL Entry in the company's base currency, matching
the rest of the dashboard (f010 Decision 9, GL-derived). Aggregation is done
with grouped SQL — one query per block, bucketed in Python — never a query per
bucket. `dashboard_summary` is the dashboard's single round-trip.

Sign conventions, deliberately different from the existing `income_by_account` /
`expense_by_account` keys: those clamp each GL row at zero, so a refund never
shows as negative income. The series blocks instead report the NET movement per
bucket, because a trend line that hides a refund inside the bucket it landed in
misreports the shape of the period. A bucket may therefore be negative.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, add_months, add_to_date, get_last_day, getdate

# The automatic ladder, by period span. Beyond the first threshold a daily
# bucket set is too dense to read and too large to ship; beyond the second, a
# monthly one is — five years of months is sixty points per series across up to
# eleven series, which is a smear rather than a trend.
#
#     up to 92 days      daily      a quarter of days still reads as a shape
#     up to 366 days     monthly    a fiscal year is twelve points
#     beyond that        yearly     multi-year comparison is a year-on-year one
#
# The second threshold is 366 rather than 365 so a fiscal year containing a leap
# day is still a year. Past it the period spans more than one year and the
# reader is asking a year-on-year question, so the buckets become years. A
# thirteen-month range therefore lands on two coarse buckets — the price of a
# rule that can be stated in one sentence, and the control is right there for
# anyone who wants the months back.
#
# WEEKLY IS NEVER CHOSEN AUTOMATICALLY. Every span it would suit is already
# covered by a neighbour — 92 days of days reads fine, a year of months reads
# better than a year of 53 weeks — so it exists for the reader who explicitly
# wants it and is not something the server should impose.
#
# daily_spend is NOT affected by any of this — the heatmap is a year grid by
# nature and always wants days (C5.8).
DAILY_GRANULARITY_MAX_DAYS = 92
MONTHLY_GRANULARITY_MAX_DAYS = 366

# The bucket widths the series can be drawn at. `auto` is not one of them: it is
# a request the client makes, resolved here into one of these three before
# anything is bucketed, so every consumer of a series sees a concrete width.
GRANULARITY_DAILY = "daily"
GRANULARITY_WEEKLY = "weekly"
GRANULARITY_MONTHLY = "monthly"
GRANULARITY_YEARLY = "yearly"
# Ordered narrowest to widest. The widening loop in `resolve_granularity` walks
# this list, so the order is load-bearing, not cosmetic.
GRANULARITIES = (
    GRANULARITY_DAILY,
    GRANULARITY_WEEKLY,
    GRANULARITY_MONTHLY,
    GRANULARITY_YEARLY,
)

# A guard on the explicit choice, not on the automatic one. Daily buckets over a
# ten-year custom range would be ~3650 points per series across up to eleven
# series — slow to ship and unreadable once drawn. Past this the request is
# widened one step at a time and the surface is told, rather than the server
# quietly honouring something the chart cannot render.
MAX_BUCKETS = 400

# How many category / account series survive before the rest is folded into a
# single "(Other)" series. Matches the top-N used by the existing scalar
# breakdowns so the dashboard is internally consistent.
TOP_N_SERIES = 10

OTHER_LABEL = "(Other)"
UNCATEGORIZED_LABEL = "(Uncategorized)"

# The balance-sheet halves the balance blocks walk. Assets alone answer "what is
# in the accounts"; net worth (c005) is meaningless without the liability side,
# so both are scanned once and split in Python.
BALANCE_ROOT_TYPES = ["Asset", "Liability"]

# Cashew's `budgets.reoccurrence` integer enum, mapped to the labels stored on
# the Cashew Budget doctype by c012. UNVERIFIED against the Cashew source: every
# row in both exports is a (3, 1) default stamp, so no observation distinguishes
# the values. Recorded as a flagged assumption (f012 D3.d / C5.5) — an
# unrecognised value raises rather than silently bucketing as monthly.
CYCLE_UNIT_DAYS = "Daily"
CYCLE_UNIT_WEEKS = "Weekly"
CYCLE_UNIT_MONTHS = "Monthly"
CYCLE_UNIT_YEARS = "Yearly"
CYCLE_UNIT_CUSTOM = "Custom"

_KNOWN_REOCCURRENCES = {
    CYCLE_UNIT_DAYS,
    CYCLE_UNIT_WEEKS,
    CYCLE_UNIT_MONTHS,
    CYCLE_UNIT_YEARS,
    CYCLE_UNIT_CUSTOM,
}

# Backstop against a pathological anchor (a daily budget anchored in 1970 with a
# 20-year window would otherwise generate ~18k cycles). Far above any real
# budget: a daily budget across a 5-year filter is ~1825 cycles.
_MAX_CYCLES = 4000


def _r(x) -> float:
    return round(float(x or 0.0), 2)


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------


def _span_days(start: date, end: date) -> int:
    """Length of the period in days, inclusive of both endpoints.

    A period_start == period_end is one day, not zero.
    """
    return (getdate(end) - getdate(start)).days + 1


def _auto_granularity(start: date, end: date) -> str:
    """The width the server picks when the client does not name one.

    See the ladder documented on the threshold constants above.
    """
    span = _span_days(start, end)
    if span <= DAILY_GRANULARITY_MAX_DAYS:
        return GRANULARITY_DAILY
    if span <= MONTHLY_GRANULARITY_MAX_DAYS:
        return GRANULARITY_MONTHLY
    return GRANULARITY_YEARLY


def _bucket_count(start: date, end: date, granularity: str) -> int:
    """How many buckets `granularity` would produce, without building them."""
    span = _span_days(start, end)
    if granularity == GRANULARITY_DAILY:
        return span
    if granularity == GRANULARITY_WEEKLY:
        return len(build_buckets(start, end, GRANULARITY_WEEKLY))
    s, e = getdate(start), getdate(end)
    if granularity == GRANULARITY_YEARLY:
        return e.year - s.year + 1
    return (e.year - s.year) * 12 + (e.month - s.month) + 1


def resolve_granularity(start: date, end: date, requested: str | None = None) -> dict:
    """Settle on one bucket width for the whole period, and say how it was chosen.

    `requested` is what the surface asked for — one of GRANULARITIES, or None /
    "auto" to leave the choice here. A named width is honoured unless it would
    produce more than MAX_BUCKETS buckets, in which case it is widened one step
    at a time. An unrecognised value is treated as no request rather than raising:
    the period is still answerable, and a dashboard that returns an error because
    a query parameter was stale helps nobody.

    Returns {granularity, requested, auto, capped} so the client can label the
    control honestly — in particular, a chart must never claim to be drawn at a
    width the reader chose when it was actually widened out from under them.
    """
    auto = _auto_granularity(start, end)
    if not requested or requested == "auto" or requested not in GRANULARITIES:
        return {
            "granularity": auto,
            "requested": "auto",
            "auto": True,
            "capped": False,
        }

    granularity = requested
    capped = False
    order = list(GRANULARITIES)
    while (
        _bucket_count(start, end, granularity) > MAX_BUCKETS
        and order.index(granularity) < len(order) - 1
    ):
        granularity = order[order.index(granularity) + 1]
        capped = True

    return {
        "granularity": granularity,
        "requested": requested,
        "auto": False,
        "capped": capped,
    }


def build_buckets(start: date, end: date, granularity: str) -> list[dict]:
    """The bucket grid for a period. Dense — every bucket exists even if empty.

    Each bucket carries its own `start`/`end` so the caller never has to
    re-derive month lengths, and the first/last buckets of the wider widths are
    CLIPPED to the period. A period starting mid-month must not attribute the
    earlier part of that month to itself, and the same holds for a mid-week
    start: the figure under a bucket label has to be a figure from inside the
    period the reader asked for.
    """
    start = getdate(start)
    end = getdate(end)
    buckets: list[dict] = []

    if granularity == GRANULARITY_DAILY:
        cursor = start
        while cursor <= end:
            buckets.append({
                "key": cursor.isoformat(),
                "label": cursor.isoformat(),
                "start": cursor.isoformat(),
                "end": cursor.isoformat(),
            })
            cursor = add_days(cursor, 1)
        return buckets

    if granularity == GRANULARITY_WEEKLY:
        # Weeks start Monday, matching the heatmap's `firstDay: 1` and ISO. The
        # cursor walks whole weeks from the Monday on or before the period start
        # so the key is stable no matter which day the period happens to open on.
        cursor = add_days(start, -start.weekday())
        while cursor <= end:
            week_end = add_days(cursor, 6)
            buckets.append({
                "key": cursor.isoformat(),
                "label": cursor.strftime("%-d %b"),
                "start": max(cursor, start).isoformat(),
                "end": min(week_end, end).isoformat(),
            })
            cursor = add_days(cursor, 7)
        return buckets

    if granularity == GRANULARITY_YEARLY:
        cursor = start.replace(month=1, day=1)
        while cursor <= end:
            year_end = cursor.replace(month=12, day=31)
            buckets.append({
                "key": cursor.isoformat(),
                "label": str(cursor.year),
                "start": max(cursor, start).isoformat(),
                "end": min(year_end, end).isoformat(),
            })
            cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
        return buckets

    cursor = start.replace(day=1)
    while cursor <= end:
        month_end = getdate(get_last_day(cursor))
        buckets.append({
            "key": cursor.isoformat(),
            "label": cursor.strftime("%b %Y"),
            "start": max(cursor, start).isoformat(),
            "end": min(month_end, end).isoformat(),
        })
        cursor = getdate(add_months(cursor, 1)).replace(day=1)
    return buckets


def bucket_key_for(posting_date: date, granularity: str) -> str:
    d = getdate(posting_date)
    if granularity == GRANULARITY_DAILY:
        return d.isoformat()
    if granularity == GRANULARITY_WEEKLY:
        return add_days(d, -d.weekday()).isoformat()
    if granularity == GRANULARITY_YEARLY:
        return d.replace(month=1, day=1).isoformat()
    return d.replace(day=1).isoformat()


# ---------------------------------------------------------------------------
# daily_spend
# ---------------------------------------------------------------------------


def daily_spend(company: str, start: str, end: str) -> list[dict]:
    """Net expense per calendar day, dense across the whole period."""
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.posting_date.as_("posting_date"),
            Sum(gl.debit).as_("debit"),
            Sum(gl.credit).as_("credit"),
        )
        .where(
            (gl.company == company)
            & (gl.posting_date[start:end])
            & (gl.is_cancelled == 0)
            & (acc.root_type == "Expense")
        )
        .groupby(gl.posting_date)
    ).run(as_dict=True)

    by_day = {
        getdate(r.posting_date).isoformat(): (r.debit or 0.0) - (r.credit or 0.0)
        for r in rows
    }

    out = []
    cursor = getdate(start)
    last = getdate(end)
    while cursor <= last:
        key = cursor.isoformat()
        out.append({"date": key, "amount": _r(by_day.get(key, 0.0))})
        cursor = add_days(cursor, 1)
    return out


# ---------------------------------------------------------------------------
# series
# ---------------------------------------------------------------------------


def period_series(
    company: str, start: str, end: str, granularity: str | None = None
) -> dict:
    """Income / expense trend, per-category breakdown, per-account balances.

    `granularity` is the surface's request — see `resolve_granularity`. Every
    block below is bucketed on the ONE width settled here, so no two charts on
    the dashboard can end up disagreeing about what a point represents.
    """
    choice = resolve_granularity(start, end, granularity)
    granularity = choice["granularity"]
    buckets = build_buckets(start, end, granularity)
    index = {b["key"]: i for i, b in enumerate(buckets)}
    size = len(buckets)

    income, expense, income_by_category, expense_by_category = _pnl_series(
        company, start, end, granularity, index, size
    )
    balances, net_worth = _balance_blocks(company, start, end, granularity, index, size)

    return {
        "granularity": granularity,
        # What the surface asked for, and whether it got it. A control that
        # silently disagrees with the chart beneath it is worse than no control.
        "granularity_requested": choice["requested"],
        "granularity_auto": choice["auto"],
        "granularity_capped": choice["capped"],
        "buckets": buckets,
        "income": income,
        "expense": expense,
        "income_by_category": income_by_category,
        "expense_by_category": expense_by_category,
        "balances": balances,
        "net_worth": net_worth,
        # The series sums, exposed so a chart never has to re-add its own bars
        # AND so the divergence from the top-level income_total / expense_total
        # is visible rather than surprising. They differ whenever an income or
        # expense account carries a reversing posting inside the period: the
        # scalars clamp each GL row at zero, these net. Any surface that shows
        # a chart total next to a tile must take both from the same place.
        "totals": {"income": _r(sum(income)), "expense": _r(sum(expense))},
    }


def _pnl_series(company, start, end, granularity, index, size):
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.posting_date.as_("posting_date"),
            acc.name.as_("account"),
            acc.account_name.as_("account_name"),
            acc.root_type.as_("root_type"),
            Sum(gl.debit).as_("debit"),
            Sum(gl.credit).as_("credit"),
        )
        .where(
            (gl.company == company)
            & (gl.posting_date[start:end])
            & (gl.is_cancelled == 0)
            & (acc.root_type.isin(["Income", "Expense"]))
        )
        .groupby(gl.posting_date, acc.name, acc.account_name, acc.root_type)
    ).run(as_dict=True)

    income = [0.0] * size
    expense = [0.0] * size
    income_by_label: dict[str, list[float]] = {}
    expense_by_label: dict[str, list[float]] = {}

    for r in rows:
        slot = index.get(bucket_key_for(r.posting_date, granularity))
        if slot is None:
            continue
        label = r.account_name or r.account or UNCATEGORIZED_LABEL
        debit = r.debit or 0.0
        credit = r.credit or 0.0
        if r.root_type == "Income":
            amount = credit - debit
            income[slot] += amount
            income_by_label.setdefault(label, [0.0] * size)[slot] += amount
        else:
            amount = debit - credit
            expense[slot] += amount
            expense_by_label.setdefault(label, [0.0] * size)[slot] += amount

    return (
        [_r(v) for v in income],
        [_r(v) for v in expense],
        _top_n_series(income_by_label, TOP_N_SERIES, size),
        _top_n_series(expense_by_label, TOP_N_SERIES, size),
    )


def _top_n_series(by_label: dict[str, list[float]], n: int, size: int) -> list[dict]:
    """Keep the n largest series by absolute total; fold the rest into (Other).

    Ranked on absolute total so a consistently negative series (a category that
    is mostly refunds) is not treated as insignificant.
    """
    ranked = sorted(by_label.items(), key=lambda kv: abs(sum(kv[1])), reverse=True)
    head, tail = ranked[:n], ranked[n:]
    out = [
        {"label": label, "total": _r(sum(values)), "values": [_r(v) for v in values]}
        for label, values in head
    ]
    if tail:
        merged = [0.0] * size
        for _label, values in tail:
            for i, v in enumerate(values):
                merged[i] += v
        out.append({
            "label": OTHER_LABEL,
            "total": _r(sum(merged)),
            "values": [_r(v) for v in merged],
            # What was folded, by name. A bare "(Other)" tells the reader an
            # amount exists but not whether it is one forgotten category or
            # thirty small ones, and the only way to find out is to leave the
            # dashboard. The members are already in hand here, so they travel
            # with the fold and the surfaces decide how much of it to show.
            "members": [
                {"label": label, "total": _r(sum(values))}
                for label, values in sorted(
                    tail, key=lambda kv: sum(kv[1]), reverse=True
                )
            ],
        })
    return out


def _balance_blocks(company, start, end, granularity, index, size):
    """Per-account closing balances (`balances`) and the net worth curve.

    Running GL sums, not a balance query per bucket: one grouped query for the
    opening cumulative as of the day before period_start, one grouped query for
    the in-period movements, then a Python prefix sum across the bucket grid.
    A bucket with no movement therefore carries the previous bucket's balance
    forward rather than dropping to zero.

    Both blocks come out of the same pair of queries. `balances` holds ASSET
    accounts only and keeps the shape c010 draws its bands from. `net_worth`
    spans Asset AND Liability, because a net worth curve computed from assets
    alone is not net worth — it would read as wealth while a loan account sat
    unmentioned beside it. Every account here is summed in its raw debit-credit
    form, so assets count positive, liabilities negative, and the plain sum is
    already the net figure. The liabilities line is negated on the way out so it
    reads as "amount owed", which is how the tooltip has to phrase it.
    """
    prior_end = add_days(getdate(start), -1)

    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")

    opening_rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            acc.name.as_("account"),
            acc.account_name.as_("account_name"),
            acc.root_type.as_("root_type"),
            Sum(gl.debit).as_("debit"),
            Sum(gl.credit).as_("credit"),
        )
        .where(
            (gl.company == company)
            & (gl.posting_date <= prior_end)
            & (gl.is_cancelled == 0)
            & (acc.root_type.isin(BALANCE_ROOT_TYPES))
        )
        .groupby(acc.name, acc.account_name, acc.root_type)
    ).run(as_dict=True)

    movement_rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.posting_date.as_("posting_date"),
            acc.name.as_("account"),
            acc.account_name.as_("account_name"),
            acc.root_type.as_("root_type"),
            Sum(gl.debit).as_("debit"),
            Sum(gl.credit).as_("credit"),
        )
        .where(
            (gl.company == company)
            & (gl.posting_date[start:end])
            & (gl.is_cancelled == 0)
            & (acc.root_type.isin(BALANCE_ROOT_TYPES))
        )
        .groupby(gl.posting_date, acc.name, acc.account_name, acc.root_type)
    ).run(as_dict=True)

    labels: dict[str, str] = {}
    root_types: dict[str, str] = {}
    opening: dict[str, float] = {}
    for r in opening_rows:
        labels[r.account] = r.account_name or r.account
        root_types[r.account] = r.root_type
        opening[r.account] = (r.debit or 0.0) - (r.credit or 0.0)

    deltas: dict[str, list[float]] = {}
    for r in movement_rows:
        slot = index.get(bucket_key_for(r.posting_date, granularity))
        if slot is None:
            continue
        labels.setdefault(r.account, r.account_name or r.account)
        root_types.setdefault(r.account, r.root_type)
        deltas.setdefault(r.account, [0.0] * size)[slot] += (r.debit or 0.0) - (r.credit or 0.0)

    running: dict[str, list[float]] = {}
    for account in labels:
        carry = opening.get(account, 0.0)
        movement = deltas.get(account, [0.0] * size)
        line = []
        for i in range(size):
            carry += movement[i]
            line.append(carry)
        running[account] = line

    net_worth = _net_worth_block(running, root_types, opening, size)

    # An account that is flat at zero across the whole window is noise on a
    # stacked chart — drop it rather than shipping a zero series per dormant
    # account in the chart of accounts.
    series = {
        labels[account]: values
        for account, values in running.items()
        if root_types.get(account) == "Asset"
        and (any(abs(v) > 0.005 for v in values) or abs(opening.get(account, 0.0)) > 0.005)
    }

    ranked = sorted(series.items(), key=lambda kv: abs(kv[1][-1]) if kv[1] else 0.0, reverse=True)
    head, tail = ranked[:TOP_N_SERIES], ranked[TOP_N_SERIES:]
    out = [
        {"label": label, "closing": _r(values[-1] if values else 0.0),
         "values": [_r(v) for v in values]}
        for label, values in head
    ]
    if tail:
        merged = [0.0] * size
        for _label, values in tail:
            for i, v in enumerate(values):
                merged[i] += v
        out.append({
            "label": OTHER_LABEL,
            "closing": _r(merged[-1] if merged else 0.0),
            "values": [_r(v) for v in merged],
            # Ranked by closing balance, the same figure the fold itself was
            # ranked on, so the list reads in the order the accounts would have
            # appeared had the chart had room for them. See the note in
            # `_top_n_series` for why the membership travels at all.
            "members": [
                {"label": label, "closing": _r(values[-1] if values else 0.0)}
                for label, values in sorted(
                    tail,
                    key=lambda kv: kv[1][-1] if kv[1] else 0.0,
                    reverse=True,
                )
            ],
        })
    return out, net_worth


def _net_worth_block(running, root_types, opening, size) -> dict:
    """Assets minus liabilities per bucket, plus the two components.

    `has_liabilities` is part of the contract rather than something the chart
    infers from an all-zero line: with `auto_settle_cash` on, this ledger books
    straight to cash and carries no payables at all, and a curve labelled "net
    worth" has to be able to say that it is, today, purely an asset curve.
    """
    assets = [0.0] * size
    liabilities = [0.0] * size
    has_liabilities = False

    for account, values in running.items():
        is_asset = root_types.get(account) == "Asset"
        target = assets if is_asset else liabilities
        for i, v in enumerate(values):
            # Liabilities are held debit-credit like everything else and negated
            # here, so the line reads as the amount owed.
            target[i] += v if is_asset else -v
        if not is_asset and (
            any(abs(v) > 0.005 for v in values) or abs(opening.get(account, 0.0)) > 0.005
        ):
            has_liabilities = True

    values = [_r(assets[i] - liabilities[i]) for i in range(size)]
    opening_total = sum(opening.values())
    return {
        "values": values,
        "assets": [_r(v) for v in assets],
        "liabilities": [_r(v) for v in liabilities],
        # The balance carried into the period, so the chart can state the change
        # over the window without pretending the first bucket started at zero.
        "opening": _r(opening_total),
        "closing": values[-1] if values else 0.0,
        "has_liabilities": has_liabilities,
    }


# ---------------------------------------------------------------------------
# budget_cycles
# ---------------------------------------------------------------------------


def cycle_boundaries(anchor, reoccurrence: str, period_length: int,
                     window_start, window_end) -> list[dict]:
    """Every budget cycle intersecting [window_start, window_end].

    Cycles are anchored on the budget's own start_date and stepped by
    `period_length` units of `reoccurrence` — a weekly budget viewed through a
    three-month filter yields ~13 cycles, not 3. The walk goes backwards from
    the anchor as well as forwards, so a filter that predates the budget's
    start_date still lines up on the budget's own grid.

    A cycle whose end falls past window_end is emitted and flagged `partial`,
    so a half-elapsed month reads as in-progress rather than as an underspend.
    """
    anchor = getdate(anchor)
    window_start = getdate(window_start)
    window_end = getdate(window_end)
    length = int(period_length or 1) or 1

    if reoccurrence not in _KNOWN_REOCCURRENCES:
        # Never guess. An unmapped Cashew enum value silently bucketed as
        # monthly would produce a budget chart that is wrong but plausible.
        frappe.throw(
            frappe._("Unrecognised budget reoccurrence {0}. Known values: {1}.").format(
                reoccurrence, ", ".join(sorted(_KNOWN_REOCCURRENCES))
            )
        )

    if reoccurrence == CYCLE_UNIT_CUSTOM:
        # Cashew's "custom" budget does not repeat — it is a single span from
        # its start_date. FLAGGED ASSUMPTION (f012 D3.d): the enum is
        # unverified, and no exported row exercises this branch.
        end = add_days(getdate(add_to_date(anchor, days=length)), -1)
        if end < window_start or anchor > window_end:
            return []
        return [{
            "start": anchor.isoformat(),
            "end": end.isoformat(),
            "partial": end > window_end,
        }]

    def step(d, direction):
        if reoccurrence == CYCLE_UNIT_DAYS:
            return getdate(add_to_date(d, days=length * direction))
        if reoccurrence == CYCLE_UNIT_WEEKS:
            return getdate(add_to_date(d, days=7 * length * direction))
        if reoccurrence == CYCLE_UNIT_MONTHS:
            return getdate(add_to_date(d, months=length * direction))
        return getdate(add_to_date(d, years=length * direction))

    # Walk back to the first cycle that still touches the window.
    cursor = anchor
    guard = 0
    while cursor > window_start and guard < _MAX_CYCLES:
        cursor = step(cursor, -1)
        guard += 1

    cycles = []
    while cursor <= window_end and len(cycles) < _MAX_CYCLES:
        nxt = step(cursor, 1)
        end = add_days(nxt, -1)
        if end >= window_start:
            cycles.append({
                "start": cursor.isoformat(),
                "end": getdate(end).isoformat(),
                "partial": getdate(end) > window_end,
            })
        cursor = nxt
    return cycles


def budget_cycles(company: str, start: str, end: str) -> list[dict]:
    """Per-budget spend bucketed on that budget's own cycle grid.

    Returns [] until c012 has created the Cashew Budget doctype — the block is
    additive and the dashboard renders without it.
    """
    budgets = _load_budgets(company)
    if not budgets:
        return []

    scope_accounts = sorted({a for b in budgets for a in b["accounts"]})
    window_start = min(getdate(b["start_date"]) for b in budgets)
    spend = _spend_by_account_day(
        company, min(getdate(start), window_start).isoformat(), end, scope_accounts
    )

    out = []
    for budget in budgets:
        cycles = cycle_boundaries(
            budget["start_date"], budget["reoccurrence"], budget["period_length"],
            start, end,
        )
        # _spend_by_account_day nets debit minus credit, which is the natural
        # direction for an expense account and the WRONG one for an income
        # account: income arrives as a credit, so a savings goal's progress
        # would come back negative and the client would draw a zero-length bar
        # under a minus-sign percentage. The budget's own is_income flag says
        # which direction counts as progress, so the flip belongs here, once,
        # rather than in each of the two surfaces that read this block.
        sign = -1 if budget["is_income"] else 1
        for cycle in cycles:
            cycle_start = getdate(cycle["start"])
            cycle_end = getdate(cycle["end"])
            spent = 0.0
            for account in budget["accounts"]:
                for day, amount in spend.get(account, {}).items():
                    if cycle_start <= day <= cycle_end:
                        spent += amount
            cycle["spent"] = _r(spent * sign)
            cycle["amount"] = _r(budget["amount"])
        out.append({
            "budget": budget["name"],
            "label": budget["label"],
            "amount": _r(budget["amount"]),
            # Cashew's own flag, carried through untouched. It is the ONLY thing
            # separating a savings goal (c009, over-target is good) from a
            # spending limit (c013, over-target is bad); the two surfaces invert
            # each other's colour treatment, so the client must never infer it
            # from the sign of the spend.
            "is_income": 1 if budget["is_income"] else 0,
            "reoccurrence": budget["reoccurrence"],
            "period_length": budget["period_length"],
            "cycles": cycles,
        })
    return out


def _load_budgets(company: str) -> list[dict]:
    """Cashew Budget rows in the shape budget_cycles needs.

    Guarded on table existence: c002 ships ahead of c012, and a dashboard that
    500s because a doctype does not exist yet is worse than one block short.
    The field names below are the contract c012 must satisfy.
    """
    if not frappe.db.table_exists("Cashew Budget"):
        return []

    rows = frappe.get_all(
        "Cashew Budget",
        filters={"company": company, "disabled": 0},
        fields=["name", "budget_name", "amount", "start_date",
                "reoccurrence", "period_length", "is_income"],
        ignore_permissions=False,
    )
    if not rows:
        return []

    scope = frappe.get_all(
        "Cashew Budget Account",
        filters={"parent": ["in", [r.name for r in rows]]},
        fields=["parent", "account"],
        # v16 names this kwarg parent_doctype; `parent` raises TypeError. The
        # branch was unreachable until c012 created the doctype, so the first
        # real budget would otherwise have 500'd the whole dashboard.
        parent_doctype="Cashew Budget",
        ignore_permissions=False,
    )
    by_budget: dict[str, list[str]] = {}
    for s in scope:
        by_budget.setdefault(s.parent, []).append(s.account)

    return [
        {
            "name": r.name,
            "label": r.budget_name or r.name,
            "amount": r.amount or 0.0,
            "start_date": r.start_date,
            "reoccurrence": r.reoccurrence,
            "period_length": r.period_length or 1,
            "is_income": r.is_income or 0,
            "accounts": by_budget.get(r.name, []),
        }
        for r in rows
        if r.start_date and by_budget.get(r.name)
    ]


# ---------------------------------------------------------------------------
# money_flow (c008)
# ---------------------------------------------------------------------------

# The three columns of the sankey, in order. A link may only ever run from one
# layer to the next, which is what makes the diagram acyclic BY CONSTRUCTION
# rather than by a cycle-breaking pass after the fact — see money_flow().
FLOW_LAYERS = ["Income", "Asset", "Expense"]

FLOW_OTHER_LABELS = {
    "Income": "(Other income)",
    "Asset": "(Other accounts)",
    "Expense": "(Other categories)",
}

# Nodes kept per layer before the rest is folded. Lower than TOP_N_SERIES: a
# sankey has to fit every node label in one column of a card, and thirty
# categories stacked in one column is a wall of text, not a diagram.
TOP_N_FLOW_NODES = 8


def money_flow(company: str, start: str, end: str) -> dict:
    """Money flow for the period as a three-column sankey.

    Income accounts -> the accounts the money landed in -> expense categories.

    HOW A LINK IS DERIVED. A GL entry knows its account and its side, not its
    counterpart, so the pairing is done per voucher: within one voucher every
    account is netted, the accounts left in credit are the sources of the money
    and the accounts left in debit are its uses, and each source is joined to
    each use in proportion to its size. On a two-legged voucher — which is what
    the Cashew importer writes for an ordinary transaction — that proportional
    split is exact. On a multi-legged voucher it is an ALLOCATION, not an
    observation: the ledger genuinely does not record which of three funding
    legs paid for which of two expenses.

    WHAT IS DELIBERATELY NOT DRAWN. Only Income->Asset and Asset->Expense links
    are kept. Everything else is excluded and reported back with its total, so
    the reader is told what is missing instead of quietly seeing a smaller
    picture:

      * transfers between two asset accounts, which move nothing into or out of
        the period's finances and, drawn, would put a link inside a single
        column and make the graph cyclic;
      * liability and equity legs — a loan drawn down or repaid;
      * income spent straight to an expense with no account in between.

    REFUNDS RUN BACKWARDS AND ARE NETTED, NOT DROPPED. A refund credits the
    expense and debits the account, which is the reverse of an allowed link. It
    is subtracted from the forward link between the same two accounts rather
    than shown as its own arrow, because a sankey arrow means "money moved this
    way" and a negative one cannot be drawn. A pair that nets to zero or below
    over the period disappears from the diagram and is reported in the excluded
    figure like everything else.
    """
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.voucher_type.as_("voucher_type"),
            gl.voucher_no.as_("voucher_no"),
            acc.name.as_("account"),
            acc.account_name.as_("account_name"),
            acc.root_type.as_("root_type"),
            Sum(gl.debit).as_("debit"),
            Sum(gl.credit).as_("credit"),
        )
        .where(
            (gl.company == company)
            & (gl.posting_date[start:end])
            & (gl.is_cancelled == 0)
        )
        .groupby(gl.voucher_type, gl.voucher_no, acc.name, acc.account_name, acc.root_type)
    ).run(as_dict=True)

    labels: dict[str, str] = {}
    root_types: dict[str, str] = {}
    vouchers: dict[tuple, dict[str, float]] = {}
    for r in rows:
        labels[r.account] = r.account_name or r.account
        root_types[r.account] = r.root_type
        key = (r.voucher_type, r.voucher_no)
        net = (r.debit or 0.0) - (r.credit or 0.0)
        vouchers.setdefault(key, {})
        vouchers[key][r.account] = vouchers[key].get(r.account, 0.0) + net

    pairs, excluded, allocated_vouchers = _flow_pairs(vouchers, root_types)

    links_raw = []
    for (src, dst), amount in pairs.items():
        if amount > 0.005:
            links_raw.append((src, dst, amount))
        else:
            # Netted to nothing or to a refund. Not drawable; still reported.
            excluded["other"] += abs(amount)

    nodes, links = _fold_flow_nodes(links_raw, labels, root_types)

    # THERE IS DELIBERATELY NO SINGLE `total`. Summing every link counts the
    # same money twice — once arriving from income and again leaving to an
    # expense — so a period with 80,000 earned and 30,000 spent would report
    # 110,000 "traced", a figure that matches nothing in the ledger. The two
    # columns are reported separately and the difference between them is real:
    # it is what stayed in the accounts.
    node_layer = {n["name"]: n["layer"] for n in nodes}
    inflow = sum(l["value"] for l in links if node_layer.get(l["source"]) == "Income")
    outflow = sum(l["value"] for l in links if node_layer.get(l["target"]) == "Expense")

    return {
        "nodes": nodes,
        "links": links,
        "inflow": _r(inflow),
        "outflow": _r(outflow),
        "allocated_vouchers": allocated_vouchers,
        "excluded": {
            "transfers": _r(excluded["transfers"]),
            "other": _r(excluded["other"]),
            "total": _r(excluded["transfers"] + excluded["other"]),
        },
    }


def _flow_pairs(vouchers, root_types):
    """Pair every voucher's sources to its uses. Pure — see money_flow().

    Returns `(pairs, excluded, allocated_vouchers)` where `pairs` maps
    (source_account, target_account) to a SIGNED amount: a forward link is
    positive, and a refund has already been subtracted from it.
    """
    pairs: dict[tuple, float] = {}
    excluded = {"transfers": 0.0, "other": 0.0}
    # Vouchers where the split was an allocation rather than an observation —
    # more than one source AND more than one use. Reported so the chart can say
    # how much of itself is inferred.
    allocated_vouchers = 0

    for legs in vouchers.values():
        uses = {a: v for a, v in legs.items() if v > 0.005}
        sources = {a: -v for a, v in legs.items() if v < -0.005}
        total_sources = sum(sources.values())
        if not uses or not sources or total_sources <= 0.005:
            continue
        if len(uses) > 1 and len(sources) > 1:
            allocated_vouchers += 1
        for src, src_amount in sources.items():
            for dst, dst_amount in uses.items():
                amount = src_amount * dst_amount / total_sources
                src_type = root_types.get(src)
                dst_type = root_types.get(dst)
                if (src_type, dst_type) in (("Income", "Asset"), ("Asset", "Expense")):
                    pairs[(src, dst)] = pairs.get((src, dst), 0.0) + amount
                elif (src_type, dst_type) in (("Asset", "Income"), ("Expense", "Asset")):
                    # A refund: same two accounts, opposite direction.
                    pairs[(dst, src)] = pairs.get((dst, src), 0.0) - amount
                elif src_type == "Asset" and dst_type == "Asset":
                    excluded["transfers"] += amount
                else:
                    excluded["other"] += amount

    return pairs, excluded, allocated_vouchers


def _fold_flow_nodes(links_raw, labels, root_types):
    """Rank each layer by throughput, fold the tail into that layer's (Other).

    Node names have to be unique across the WHOLE graph — ECharts keys sankey
    links by name, so one account name appearing in two layers would silently
    merge into a single node and put a link inside a column, which is exactly
    the cycle the layer rule exists to prevent. Any label used by more than one
    layer is therefore suffixed with its layer.
    """
    throughput: dict[str, float] = {}
    for src, dst, amount in links_raw:
        throughput[src] = throughput.get(src, 0.0) + amount
        throughput[dst] = throughput.get(dst, 0.0) + amount

    keep: dict[str, str] = {}
    layer_of: dict[str, str] = {}
    folded: list[str] = []
    for layer in FLOW_LAYERS:
        members = sorted(
            (a for a in throughput if root_types.get(a) == layer),
            key=lambda a: throughput[a],
            reverse=True,
        )
        for i, account in enumerate(members):
            if i < TOP_N_FLOW_NODES:
                keep[account] = labels.get(account, account)
            else:
                keep[account] = FLOW_OTHER_LABELS[layer]
                folded.append(account)
            layer_of[account] = layer

    # Disambiguate a label claimed by more than one layer.
    layers_per_label: dict[str, set] = {}
    for account, label in keep.items():
        layers_per_label.setdefault(label, set()).add(layer_of[account])
    names: dict[str, str] = {}
    for account, label in keep.items():
        layer = layer_of[account]
        names[account] = f"{label} ({layer.lower()})" if len(layers_per_label[label]) > 1 else label

    merged: dict[tuple, float] = {}
    for src, dst, amount in links_raw:
        key = (names[src], names[dst])
        merged[key] = merged.get(key, 0.0) + amount

    node_layer: dict[str, str] = {}
    node_value: dict[str, float] = {}
    for (src, dst), amount in merged.items():
        node_value[src] = node_value.get(src, 0.0) + amount
        node_value[dst] = node_value.get(dst, 0.0) + amount
    for account, name in names.items():
        if name in node_value:
            node_layer[name] = layer_of[account]

    # `throughput`, not `value`: for an account in the middle column this is
    # what came in PLUS what went out, which is not the account's balance and
    # must not be labelled as though it were.
    # Which accounts ended up inside each layer's "(Other)" node, keyed by that
    # node's final name. A folded sankey node is the least self-explanatory
    # thing on the diagram — a ribbon of real size arriving at a box that names
    # nothing — so it carries its membership like every other fold here.
    # Keyed off `folded`, recorded where the fold happened, rather than matched
    # back by label: the disambiguation above may have renamed the node.
    folded_into: dict[str, list] = {}
    for account in folded:
        name = names[account]
        if name not in node_value:
            continue
        folded_into.setdefault(name, []).append({
            "label": labels.get(account, account),
            "throughput": _r(throughput.get(account, 0.0)),
        })
    for members in folded_into.values():
        members.sort(key=lambda m: m["throughput"], reverse=True)

    nodes = [
        {
            "name": name,
            "layer": node_layer[name],
            "throughput": _r(value),
            **({"members": folded_into[name]} if name in folded_into else {}),
        }
        for name, value in sorted(node_value.items(), key=lambda kv: kv[1], reverse=True)
    ]
    links = [
        {"source": src, "target": dst, "value": _r(amount)}
        for (src, dst), amount in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return nodes, links


def _spend_by_account_day(company: str, start: str, end: str,
                          accounts: list[str]) -> dict[str, dict[date, float]]:
    if not accounts:
        return {}
    gl = frappe.qb.DocType("GL Entry")
    rows = (
        frappe.qb.from_(gl)
        .select(
            gl.account.as_("account"),
            gl.posting_date.as_("posting_date"),
            Sum(gl.debit).as_("debit"),
            Sum(gl.credit).as_("credit"),
        )
        .where(
            (gl.company == company)
            & (gl.posting_date[start:end])
            & (gl.is_cancelled == 0)
            & (gl.account.isin(accounts))
        )
        .groupby(gl.account, gl.posting_date)
    ).run(as_dict=True)

    out: dict[str, dict[date, float]] = {}
    for r in rows:
        out.setdefault(r.account, {})[getdate(r.posting_date)] = (
            (r.debit or 0.0) - (r.credit or 0.0)
        )
    return out
