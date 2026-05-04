from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaudit.cli import collect_capabilities, main


class CliTests(unittest.TestCase):
    def test_collect_capabilities_includes_python(self) -> None:
        components = {cap.component for cap in collect_capabilities()}
        self.assertIn("Python", components)

    def test_version_command(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            main(["version"])
        self.assertIn("scaudit 0.1.0", output.getvalue())

    def test_help_command(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            main(["--help"])
        self.assertIn("scaudit", output.getvalue())
        self.assertIn("doctor", output.getvalue())


if __name__ == "__main__":
    unittest.main()
