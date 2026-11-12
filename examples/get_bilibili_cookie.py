from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conf import BASE_DIR


if __name__ == "__main__":
    # Best to run this script directly in a real local terminal.
    # If the QR code in the terminal is displayed incompletely, open qrcode.png in the current directory and scan it.
    cli_path = Path(BASE_DIR) / "sau_cli.py"
    subprocess.run(
        [
            sys.executable,
            str(cli_path),
            "bilibili",
            "login",
            "--account",
            "creator",
        ],
        check=True,
    )
