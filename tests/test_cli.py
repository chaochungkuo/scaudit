from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaudit.config import load_config, validate_config
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

    def test_init_config_writes_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            output = io.StringIO()
            with redirect_stdout(output):
                main(["init-config", "input.h5ad", "--format", "toml", "--out", str(config_path)])
            self.assertTrue(config_path.exists())
            config = load_config(config_path)
            self.assertEqual(config["dataset"]["path"], "input.h5ad")
            self.assertIn("validate", output.getvalue())

    def test_validate_config_reports_missing_dataset_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            with redirect_stdout(io.StringIO()):
                main(["init-config", "missing.h5ad", "--out", str(config_path)])
            items = validate_config(config_path)
            statuses = {item.section: item.status for item in items}
            self.assertEqual(statuses["dataset.path"], "WARN")

    def test_plan_command_outputs_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            with redirect_stdout(io.StringIO()):
                main(["init-config", "input.h5ad", "--out", str(config_path)])
            output = io.StringIO()
            with redirect_stdout(output):
                main(["plan", str(config_path)])
            self.assertIn("Stages", output.getvalue())
            self.assertIn("annotation_cards.json", output.getvalue())


if __name__ == "__main__":
    unittest.main()
