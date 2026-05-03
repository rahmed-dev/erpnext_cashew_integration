"""
Single entry point for writing per-row validation errors.

Stamps `[Row {row_idx}] ` prefix on the message at write time so the prefix
travels with the row everywhere it surfaces (in-grid, diagnostics CSV, Vue
Row Explorer modal, copy-paste, support tickets) without a separate display
layer.

File-level errors (no row_idx) bypass the prefix — pre-row failures like
encoding / missing-column / empty-file have no row context.

Double-prefix protection: if message already starts with `[Row `, store as-is.
Necessary for option-b validate-time re-evaluation (c002) which can re-fire
the same error site within a single user action.
"""

from typing import Optional


def prefix_with_row_idx(row: Optional[dict], msg: str) -> str:
    """Return ``msg`` with ``[Row {row_idx}] `` prefix when *row* has a row_idx
    and the message is not already prefixed. Use for non-Error writes (Skipped,
    informational) where ``set_row_validation_error`` is the wrong fit."""
    if not msg or msg.startswith("[Row "):
        return msg
    if row is None:
        return msg
    row_idx = row.get("row_idx")
    if not row_idx:
        return msg
    return f"[Row {row_idx}] {msg}"


def set_row_validation_error(row: Optional[dict], code: str, msg: str) -> None:
    """Set ``validation_status``, ``validation_error_code``, and a row-prefixed
    ``validation_error_message`` on *row*.

    No-op when *row* is None — caller handles file-level errors via
    ``Cashew Import Run.error_log`` or equivalent.
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
