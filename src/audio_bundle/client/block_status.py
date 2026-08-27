from __future__ import annotations


def block_status_icon(*, unlocked: bool, opened: bool, sequence_locked: bool) -> str:
    """Lock/unlock marks for Client blocks. Folders never use these."""
    if unlocked:
        return "🔓"
    if opened:
        return "✓"
    if sequence_locked:
        return "🔒"
    return "🔓"
