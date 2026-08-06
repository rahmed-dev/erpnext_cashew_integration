// f012 c009 / c013 — shared reading of the `budget_cycles` block.
//
// Both budget surfaces face the same two questions — which budgets are mine to
// draw, and does this filter span one cycle or several — and they must answer
// them identically, because a savings goal and a spending limit that disagree
// about what a cycle is would be describing two different months.
//
// D3.d, binding: a target is NEVER pro-rated. A monthly budget seen through a
// half-month filter still shows its full cycle amount, and the cycle is marked
// as unfinished instead. A pro-rated target is a number that exists nowhere in
// Cashew and that no one set.

/** Income budgets are savings goals (c009); the rest are spending limits (c013). */
export function selectBudgets(cycles, { income }) {
  return (cycles || []).filter(
    (b) => !!b.is_income === income && (b.amount || 0) > 0.005 && (b.cycles || []).length > 0,
  );
}

/** `Mar 2026` for a whole month, `3 Mar – 9 Mar 2026` otherwise. */
export function cycleLabel(cycle) {
  const start = new Date(`${cycle.start}T00:00:00`);
  const end = new Date(`${cycle.end}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return cycle.start;

  const wholeMonth =
    start.getDate() === 1 &&
    end.getMonth() === start.getMonth() &&
    end.getFullYear() === start.getFullYear() &&
    new Date(end.getFullYear(), end.getMonth() + 1, 0).getDate() === end.getDate();
  if (wholeMonth) {
    return start.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
  }
  const opts = { day: 'numeric', month: 'short' };
  return `${start.toLocaleDateString(undefined, opts)} – ${end.toLocaleDateString(undefined, { ...opts, year: 'numeric' })}`;
}

/** Progress against the cycle target, as a percentage. Never clipped at 100. */
export function cyclePercent(cycle) {
  const target = cycle.amount || 0;
  if (target <= 0.005) return 0;
  return ((cycle.spent || 0) / target) * 100;
}

/** How the reader should be told a budget repeats. */
export function reoccurrenceLabel(budget) {
  const every = budget.period_length || 1;
  const unit = String(budget.reoccurrence || '').toLowerCase();
  const noun = { daily: 'day', weekly: 'week', monthly: 'month', yearly: 'year' }[unit];
  if (!noun) return unit === 'custom' ? 'one-off' : unit;
  return every === 1 ? `per ${noun}` : `every ${every} ${noun}s`;
}
