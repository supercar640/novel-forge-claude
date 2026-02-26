# -*- coding: utf-8 -*-
"""Novel Forge Claude - entry point."""

import sys
import io
from pathlib import Path

# Windows UTF-8 output
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace"
    )

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nfc.cli import main
from nfc.interactive import run as interactive_run

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        interactive_run()
    else:
        main()
