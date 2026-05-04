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

    def test_diagnose_writes_json_for_placeholder_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.h5ad"
            input_path.write_text("placeholder", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                main(["diagnose", str(input_path), "--cluster-key", "leiden", "--out", str(temp_path / "results")])
            self.assertTrue((temp_path / "results" / "diagnosis.json").exists())

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

    def test_run_command_writes_output_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.toml"
            with redirect_stdout(io.StringIO()):
                main(["init-config", "input.h5ad", "--out", str(config_path)])
            text = config_path.read_text(encoding="utf-8")
            text = text.replace('dir = "results"', f'dir = "{temp_path / "results"}"')
            config_path.write_text(text, encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                main(["run", str(config_path)])

            output_dir = temp_path / "results"
            self.assertTrue((output_dir / "config.resolved.toml").exists())
            self.assertTrue((output_dir / "annotation_cards.json").exists())
            self.assertTrue((output_dir / "review_table.csv").exists())
            self.assertTrue((output_dir / "report" / "index.html").exists())

    def test_finalize_command_writes_final_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.toml"
            with redirect_stdout(io.StringIO()):
                main(["init-config", "input.h5ad", "--out", str(config_path)])
            text = config_path.read_text(encoding="utf-8")
            text = text.replace('dir = "results"', f'dir = "{temp_path / "results"}"')
            config_path.write_text(text, encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                main(["run", str(config_path)])

            final_dir = temp_path / "final"
            with redirect_stdout(io.StringIO()):
                main(["finalize", str(temp_path / "results"), "--out", str(final_dir)])

            self.assertTrue((final_dir / "final_annotation_cards.json").exists())
            self.assertTrue((final_dir / "final_annotation_summary.csv").exists())
            self.assertTrue((final_dir / "review_audit.json").exists())
            self.assertTrue((final_dir / "report" / "index.html").exists())

    def test_review_import_writes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.toml"
            with redirect_stdout(io.StringIO()):
                main(["init-config", "input.h5ad", "--out", str(config_path)])
            text = config_path.read_text(encoding="utf-8")
            text = text.replace('dir = "results"', f'dir = "{temp_path / "results"}"')
            config_path.write_text(text, encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                main(["run", str(config_path)])

            review_table = temp_path / "results" / "review_table.csv"
            with review_table.open("a", encoding="utf-8") as handle:
                handle.write("4,Cardiomyocyte,Accepted,high,accepted,Cardiomyocyte,\n")

            with redirect_stdout(io.StringIO()):
                main(["review", "import", str(review_table), "--run", str(temp_path / "results")])

            self.assertTrue((temp_path / "results" / "reviewed_review_table.csv").exists())
            self.assertTrue((temp_path / "results" / "review_audit.json").exists())

    def test_reference_add_and_use(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.toml"
            ref_path = temp_path / "ref.h5ad"
            ref_path.write_text("placeholder", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                main(["init-config", "input.h5ad", "--out", str(config_path)])

            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_path)
                with redirect_stdout(io.StringIO()):
                    main(
                        [
                            "reference",
                            "add",
                            str(ref_path),
                            "--id",
                            "my_ref",
                            "--species",
                            "mouse",
                            "--tissue",
                            "heart",
                            "--label-key",
                            "cell_type",
                        ]
                    )
                with redirect_stdout(io.StringIO()):
                    main(["reference", "use", "my_ref", "--config", str(config_path)])
                output = io.StringIO()
                with redirect_stdout(output):
                    main(["reference", "list"])
            finally:
                os.chdir(old_cwd)

            self.assertTrue((temp_path / "references" / "registry.json").exists())
            self.assertIn('selected = ["my_ref"]', config_path.read_text(encoding="utf-8"))
            self.assertIn("my_ref", output.getvalue())


if __name__ == "__main__":
    unittest.main()
