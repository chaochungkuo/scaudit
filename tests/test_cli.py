from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaudit.config import load_config, validate_config
from scaudit.cli import collect_capabilities, main
from scaudit.data import infer_gene_id_counts, infer_gene_id_type, summarize_cluster_key
from scaudit.llm import OpenAICompatibleClient, enrich_cards_with_llm
from scaudit.markers import attach_marker_evidence, marker_rows_from_rank_genes_groups
from scaudit.report import render_draft_report
from scaudit.run import _llm_settings, build_annotation_cards


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
            diagnosis_path = temp_path / "results" / "diagnosis.json"
            self.assertTrue(diagnosis_path.exists())
            diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
            self.assertIn("gene_id_type", diagnosis)
            self.assertIn("gene_id_counts", diagnosis)
            self.assertIn("matrix", diagnosis)
            self.assertIn("qc_metadata", diagnosis)
            self.assertIn("cluster_diagnostics", diagnosis)

    def test_gene_id_detection_prefers_dominant_identifier_type(self) -> None:
        human_counts = infer_gene_id_counts(
            [
                "ENSG000001",
                "ENSG000002",
                "ENSG000003",
                "ENSG000004",
                "ENSG000005",
                "ENSG000006",
                "ENSG000007",
                "ENSG000008",
                "ENSG000009",
                "ACTB",
            ]
        )
        symbol_counts = infer_gene_id_counts(["Actb", "Gapdh", "Mki67"])
        mixed_counts = infer_gene_id_counts(["ENSG000001", "ENSMUSG0000001", "ACTB"])

        self.assertEqual(infer_gene_id_type(human_counts), "human_ensembl")
        self.assertEqual(infer_gene_id_type(symbol_counts), "symbol")
        self.assertEqual(infer_gene_id_type(mixed_counts), "mixed")

    def test_cluster_diagnostics_flags_tiny_and_missing_clusters(self) -> None:
        diagnosis = summarize_cluster_key({"0": 25, "1": 8}, missing_values=2)

        self.assertEqual(diagnosis["missing_values"], 2)
        self.assertEqual(diagnosis["min_cluster_size"], 8)
        self.assertEqual(diagnosis["max_cluster_size"], 25)
        self.assertEqual(diagnosis["tiny_clusters"], ["1"])
        self.assertFalse(diagnosis["suitable_for_cluster_level_audit"])

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
            self.assertTrue((output_dir / "marker_evidence.csv").exists())
            self.assertTrue((output_dir / "annotation_cards.json").exists())
            self.assertTrue((output_dir / "review_table.csv").exists())
            self.assertTrue((output_dir / "report" / "report.html").exists())
            self.assertTrue((output_dir / "report" / "review.html").exists())

    def test_build_annotation_cards_from_cluster_sizes(self) -> None:
        cards = build_annotation_cards({"cluster_sizes": {"0": 10, "1": 12}})
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["decision"], "Needs review")
        self.assertEqual(cards[0]["provenance"]["cell_count"], 10)

    def test_marker_rows_from_rank_genes_groups(self) -> None:
        rows = marker_rows_from_rank_genes_groups(
            {
                "names": {"0": ["Lyz2", "C1qa"], "1": ["Acta2"]},
                "scores": {"0": [8.5, 7.2], "1": [6.0]},
                "logfoldchanges": {"0": [1.4, 1.1], "1": [2.0]},
                "pvals": {"0": [0.01, 0.02], "1": [0.03]},
                "pvals_adj": {"0": [0.05, 0.06], "1": [0.07]},
            },
            top_n=2,
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["cluster_id"], "0")
        self.assertEqual(rows[0]["gene"], "Lyz2")
        self.assertEqual(rows[0]["rank"], 1)

    def test_attach_marker_evidence_updates_cards(self) -> None:
        cards = build_annotation_cards({"cluster_sizes": {"0": 10}})
        updated = attach_marker_evidence(
            cards,
            [
                {
                    "cluster_id": "0",
                    "rank": 1,
                    "gene": "Lyz2",
                    "score": 8.5,
                    "logfoldchange": 1.4,
                    "pvalue": 0.01,
                    "pvalue_adj": 0.05,
                }
            ],
        )

        self.assertEqual(updated[0]["evidence"]["markers"][0]["gene"], "Lyz2")
        self.assertIn("Marker evidence", updated[0]["reasoning"]["summary"])

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
            self.assertTrue((final_dir / "report" / "report.html").exists())

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

    def test_annotate_command_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.h5ad"
            input_path.write_text("placeholder", encoding="utf-8")
            output_dir = temp_path / "annotated"
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "annotate",
                        str(input_path),
                        "--cluster-key",
                        "leiden",
                        "--out",
                        str(output_dir),
                        "--no-llm",
                    ]
                )
            self.assertTrue((output_dir / "annotation_cards.json").exists())
            self.assertTrue((output_dir / "review_table.csv").exists())
            self.assertTrue((output_dir / "report" / "report.html").exists())

    def test_marker_db_lookup(self) -> None:
        from scaudit.markers import lookup_cell_type

        matches = lookup_cell_type({"CD3D", "CD3E", "CD8A", "CD8B", "GZMB"})
        self.assertTrue(len(matches) > 0)
        top = matches[0]
        self.assertIn("label", top)
        self.assertIn("jaccard", top)
        self.assertGreater(top["jaccard"], 0)

    def test_report_umap_has_cluster_confidence_and_sample_tabs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            diagnosis_path = temp_path / "diagnosis.json"
            cards_path = temp_path / "annotation_cards.json"
            report_dir = temp_path / "report"
            diagnosis_path.write_text(
                json.dumps(
                    {
                        "path": "input.h5ad",
                        "n_obs": 2,
                        "n_vars": 3,
                        "cluster_count": 1,
                        "warnings": [],
                        "umap_coords": {"0": {"x": [0.0, 1.0], "y": [0.0, 1.0], "sample": ["s1", "s2"]}},
                    }
                ),
                encoding="utf-8",
            )
            cards_path.write_text(
                json.dumps(
                    [
                        {
                            "cluster_id": "0",
                            "proposed_label": "T cell",
                            "decision": "Needs review",
                            "confidence": {"overall": "medium", "lineage": "medium", "subtype": "unknown"},
                            "evidence": {"markers": [], "models": [], "references": [], "ontology": [], "qc_warnings": []},
                            "reasoning": {"summary": "review", "supports": [], "contradictions": [], "uncertainties": [], "validation_suggestions": []},
                            "provenance": {"cell_count": 2},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            report_path = render_draft_report(report_dir, diagnosis_path, cards_path)
            html = report_path.read_text(encoding="utf-8")

            self.assertIn('data-umap-mode="cluster"', html)
            self.assertIn('data-umap-mode="confidence"', html)
            self.assertIn('data-umap-mode="sample"', html)
            self.assertIn("window.scauditUMAPTraces", html)

    def test_llm_settings_reads_config_values(self) -> None:
        settings = _llm_settings(
            {
                "llm": {
                    "provider": "openai",
                    "base_url": "https://chat.kiconnect.nrw/api/v1",
                    "api_key_env": "KICONNECT_API_KEY",
                    "model": "test-model",
                    "temperature": 0.2,
                }
            }
        )

        self.assertEqual(settings["provider"], "openai")
        self.assertEqual(settings["base_url"], "https://chat.kiconnect.nrw/api/v1")
        self.assertEqual(settings["api_key_env"], "KICONNECT_API_KEY")
        self.assertEqual(settings["model"], "test-model")
        self.assertEqual(settings["temperature"], 0.2)

    def test_openai_compatible_llm_updates_summary(self) -> None:
        class FakeClient(OpenAICompatibleClient):
            def __init__(self) -> None:
                self.kwargs = {}
                pass

            def complete(self, **kwargs):
                self.kwargs = kwargs
                return "Grounded summary."

        cards = [
            {
                "cluster_id": "0",
                "decision": "Needs review",
                "confidence": {"lineage": "medium", "subtype": "unknown", "overall": "medium"},
                "evidence": {"markers": [{"gene": "CD3D", "log2fc": 1.2}], "models": [], "references": []},
                "reasoning": {"summary": "old", "supports": [], "uncertainties": [], "contradictions": []},
                "provenance": {"cell_count": 10},
            }
        ]

        client = FakeClient()
        with patch.dict(os.environ, {"KICONNECT_API_KEY": "token"}), patch("scaudit.llm._build_client", return_value=client):
            enrich_cards_with_llm(
                cards,
                provider="openai",
                base_url="https://chat.kiconnect.nrw/api/v1",
                api_key_env="KICONNECT_API_KEY",
                model="model",
                temperature=0,
            )

        self.assertEqual(cards[0]["reasoning"]["summary"], "Grounded summary.")
        self.assertEqual(client.kwargs["model"], "model")

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
