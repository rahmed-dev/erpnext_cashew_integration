# f010 — Architecture Decisions (Shard B)

> Continuation of `decisions.md` (Shard A reached 462 lines). All decisions remain
> authoritative; this shard captures amendments and new decisions recorded after
> Shard A was sealed.

## Amendment 1 to D13 / D14 — Custom accent color escape hatch (2026-05-24, TD phase)

**Amends:** D13.1 (`Cashew Settings.accent_color` field), D14 (theming pipeline).

**Decision:** The 5-preset cap on `accent_color` is opened. The Select field gains a
sixth choice `Custom`, and a paired `Data` field `accent_color_custom` holds the
user-supplied hex when `Custom` is selected. Curated presets (Indigo / Teal /
Burnt Orange / Monochrome / Cyan) keep designer-tuned shade tables; `Custom`
triggers runtime HSL-based shade derivation in the SPA shell.

**Why:** User direction (TD phase, 2026-05-24). The 5-preset cap was arbitrary —
five values felt safe but provided no escape hatch for branding edge cases
(personal preference, agency engagement, dark-mode experiment). Custom retains
the curated default path while removing the lock-in. Schema cost is one extra
field; runtime cost is ~15 lines of HSL math in the shell.

**What changes:**

1. **`Cashew Settings.accent_color`** — Options list grows from 5 to 6:
   ```
   Indigo
   Teal
   Burnt Orange
   Monochrome
   Cyan
   Custom
   ```
   Default still `Indigo`.

2. **New field `Cashew Settings.accent_color_custom`** (added to c013):
   - Fieldtype: `Data`
   - `depends_on: eval:doc.accent_color=='Custom'`
   - `mandatory_depends_on: eval:doc.accent_color=='Custom'`
   - Server-side validator (in `Cashew Settings.validate()`): regex
     `^#[0-9a-fA-F]{6}$`; rejects anything else with a clear error.
   - Placement: immediately after `accent_color`.

3. **D14 theming pipeline** — shell logic at SPA boot + on settings save:
   ```
   if accent_color == "Custom" and valid hex:
       base = accent_color_custom
       shades = deriveShades(base)   # HSL math, see below
   else:
       base, shades = PRESET_TABLE[accent_color]
   ```
   The 4 CSS custom properties (`--cs-accent`, `--cs-accent-700`,
   `--cs-accent-100`, `--cs-accent-50`) are set on `<html>` either way.

4. **Shade derivation function** (lives in c004 shell, not c013):
   - Parse hex → HSL.
   - `--cs-accent` = base.
   - `--cs-accent-700` = `hsl(h, s, max(0, l - 10%))`.
   - `--cs-accent-100` = `hsl(h, min(s, 30%), 92%)`.
   - `--cs-accent-50` = `hsl(h, min(s, 20%), 96%)`.
   - Output back to hex for CSS.
   These coefficients deliberately mirror the Tailwind shade family pattern;
   they are pragmatic approximations, not perceptually-tuned values. Acceptable
   for an operator tool; revisit if Designer flags contrast issues.

5. **Settings page (c012)** — Appearance section gains a `Custom hex` text input
   that appears only when `Custom` is selected in the preset grid. Input
   validates client-side with the same hex regex; pasting a non-hex string
   shakes the input + shows inline error. Save button disables until valid.

**Realtime:** No change. Same `Cashew Settings` doc_update subscription
propagates both fields to other open tabs (D14 + D8).

**Permissions:** No change. `accent_color_custom` inherits Cashew Settings
write perms.

**Migration impact:** None new beyond c013's existing `bench migrate` step.
Adding a 6th option to an existing Select field + adding one new Data field
are both purely additive.

**Open within this amendment:**
- Whether to expose a hex eye-dropper or color-wheel in the Settings UI (vs.
  free-text hex input). **Default for c012 spec:** simple hex text input +
  preview swatch. Eye-dropper is a c012-spec-time follow-up.
- Whether to validate `accent_color_custom` for sufficient contrast against
  white text (`#fff`) on the resulting button bg. **Default:** no — operator
  responsibility. Revisit if a11y flag raised.

**Status:** **approved 2026-05-24, TD phase.** Locked-in for c013 + c012 + c004.
