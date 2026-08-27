from __future__ import annotations


def block_status_icon(*, unlocked: bool, opened: bool, sequence_locked: bool) -> str:
    """Lock/unlock marks for Client blocks. Folders never use these.

    Every block starts locked (including the first block in a day). The open
    lock is shown only after the Client has actually unlocked it.
    """
    if unlocked:
        return "🔓"
    if opened:
        return "✓"
    return "🔒"
