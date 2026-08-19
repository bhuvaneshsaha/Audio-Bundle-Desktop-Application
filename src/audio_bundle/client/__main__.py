"""Client desktop application."""

from __future__ import annotations

import logging
import sys


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        from audio_bundle.client.app import run
    except ImportError:
        raise SystemExit(
            "PySide6 is required for the Client application. Install with: pip install -e '.[ui]'"
        ) from None
    raise SystemExit(run(sys.argv))


if __name__ == "__main__":
    main()
