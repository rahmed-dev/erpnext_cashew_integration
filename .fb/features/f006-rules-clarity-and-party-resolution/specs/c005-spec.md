# Spec: c005 — validation-error-prefix

Story: [c005-story.md](./c005-story.md)
Architecture: f006 Decision 5.

## Overview

Mechanical change touching every site that writes `validation_error_message`. Centralize through one helper that stamps `[Row {row_idx}] ` prefix; update call sites to use it. Confirm + extend diagnostics CSV column set if needed.

## Component Detail

```yaml
id: c005
name: validation-error-prefix
type: backend-module
depends_on: [c001]
```

## TD Decisions

1. **One shared helper**, not per-module string formatting. Single source of truth = single place to change format later.
2. **Prefix added at write time**, not display time. Per Decision 5: the message must remain useful when copied into logs, diagnostics, support tickets, hover.
3. **No prefix for file-level (pre-row) errors.** Encoding errors, missing required columns, empty file — no `row_idx`. Helper accepts an optional `row` arg; when absent, no prefix.
4. **`validation_error_code` field stays untouched.** Only the message string shape changes. No new codes.
5. **Diagnostics CSV format change is additive.** Add `row_idx` column at the front if missing. Old diagnostics files on prior runs stay readable as-is.
6. **Defensive double-prefix prevention.** Helper checks if message already starts with `[Row ` and skips re-prefixing — protects against re-validation flows (c002 option b validate-time re-evaluation could fire same error twice across calls).

## Function Spec

```python
# cashew_integration/importer/errors.py

from typing import Optional

def set_row_validation_error(
    row: Optional[dict],
    code: str,
    msg: str,
) -> None:
    """Single entry point for writing a validation error onto a parsed row.
    Stamps validation_status='Error', validation_error_code, and a row-prefixed
    validation_error_message.

    If row is None, helper is a no-op on row state — caller handles file-level
    errors via Cashew Import Run.error_log or equivalent.
    """
    if row is None:
        return

    row["validation_status"] = "Error"
    row["validation_error_code"] = code

    if msg.startswith("[Row "):
        row["validation_error_message"] = msg
        return

    row_idx = row.get("row_idx")
    if row_idx:
        row["validation_error_message"] = f"[Row {row_idx}] {msg}"
    else:
        row["validation_error_message"] = msg
```

## Files Affected

| file | change |
|---|---|
| `cashew_integration/importer/errors.py` | NEW. `set_row_validation_error` helper. |
| `cashew_integration/importer/parser.py` | Replace `_error(row, code, msg)` body to delegate to shared helper (or rename). All call sites unchanged at the call boundary. |
| `cashew_integration/importer/mapping.py` | Replace direct `row["validation_error_message"] = ...` writes with helper calls. Includes existing `EXTERNAL_ACCOUNT_NOT_MAPPED`, `CATEGORY_NOT_MAPPED`, etc. |
| `cashew_integration/importer/validation.py` | Replace direct writes with helper calls. Includes new `CATEGORY_ACCOUNT_CLASS_MISMATCH` site from c001. |
| `cashew_integration/importer/idempotency.py` | If duplicate-skip writes a message, route through helper. |
| `cashew_integration/importer/worker.py` | Posting-stage failures (ERP doc creation errors) routed through helper so async-worker errors carry the prefix. |
| diagnostics CSV writer (Dev locates — likely `worker.py` or sibling) | Confirm `row_idx` is the first column. Add if missing. |

## Data Flow

```mermaid
flowchart LR
    A[parser / mapping / validation /<br/>idempotency / worker]
    A -->|set_row_validation_error| B[errors.py helper]
    B --> CD{row None?}
    CD -->|yes| Z[no-op]
    CD -->|no| C{message already<br/>prefixed?}
    C -->|yes| F2[store as-is]
    C -->|no| C2{row has row_idx?}
    C2 -->|yes| D[message = '[Row N] ' + msg]
    C2 -->|no| E[message = msg]
    D --> F[row.validation_error_message]
    E --> F
    F2 --> F
    F --> G[Cashew Import Row]
    G --> H[in-grid display]
    G --> I[diagnostics CSV<br/>row_idx column + message]
    G --> J[Vue Row Explorer modal]
    G --> K[copy-paste / logs / tickets]
```

## Permissions

No change.

## Frappe Hooks

None.

## Notes / Gotchas

- **Double-prefix prevention is essential** for c002 option b — validate-time re-evaluation can call the same error site twice. `startswith("[Row ")` check absorbs this idempotently.
- **Posting-stage worker errors carry row context.** When ERP doc creation fails in the queue worker, helper writes prefix automatically — async errors are no harder to read than parse-time ones.
- **No migration on existing rows.** Already-stored unprefixed messages on prior runs stay as-is — old runs are frozen per f004 revert principle.
- **Tests updated, not rewritten.** Bulk-grep tests for `validation_error_message` and switch assertions to substring match (`assert "Account X" in msg`) where possible — survives prefix change, more durable across future format tweaks.
- **No new error codes.**

## Testing Notes (Dev Hand-off)

- Unit test for helper: row with row_idx → prefixed; row without row_idx → unprefixed; row=None → no-op; double-prefix prevention (call twice with same message).
- Update existing test_parser / test_mapping / test_integration assertions to expect prefix or use substring match.
- Diagnostics CSV test: trigger a run with at least one validation error, download `diagnostics_file`, assert `row_idx` is a column AND `validation_error_message` text contains `[Row N]`.

status: approved
