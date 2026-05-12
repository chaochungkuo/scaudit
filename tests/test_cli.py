from __future__ import annotations

import io
import importlib.util
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
from scaudit.data import ClusterEvidence, MarkerGene, _fill_composition_evidence, _fill_marker_signature_evidence, _qc_metric_warning, _reference_gene_warnings, infer_gene_id_counts, infer_gene_id_type, summarize_cluster_key
from scaudit.llm import OpenAICompatibleClient, enrich_cards_with_llm
from scaudit.markers import attach_marker_evidence, marker_rows_from_rank_genes_groups
from scaudit.providers.marker_based import write_marker_provider_outputs
from scaudit.providers.external_annotation import write_external_annotation_provider_outputs
from scaudit.providers.reference_mapping import write_reference_provider_outputs
from scaudit.report import render_draft_report
from scaudit.run import _assign_annotation, _llm_settings, build_annotation_cards


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

    def test_reference_gene_warnings_flag_identifier_mismatch_and_low_overlap(self) -> None:
        warnings = _reference_gene_warnings(
            "ref_a",
            "symbol",
            "human_ensembl",
            {"0": {"CD3D", "CD3E"}, "1": {"MS4A1"}},
            {"ENSG000001", "ENSG000002"},
        )

        self.assertIn("Reference ref_a gene ID type is human_ensembl", warnings[0])
        self.assertIn("Only 0% of query marker genes were found in reference ref_a", warnings[1])

    def test_qc_warning_can_trigger_artifact_decision(self) -> None:
        warning = _qc_metric_warning(
            "pct_counts_mt",
            "0",
            {"mean": 25.0, "median": 22.0},
            {"mean": 8.0, "median": 7.0},
        )

        self.assertIsNotNone(warning)
        proposed_label, decision, confidence, reasoning, uncertainty = _assign_annotation(
            cluster_id="0",
            cell_count=100,
            markers=[],
            celltypist_label=None,
            celltypist_prob=None,
            ref_matches=[],
            qc_warnings=[str(warning)],
        )

        self.assertIsNone(proposed_label)
        self.assertEqual(decision, "Artifact warning")
        self.assertEqual(confidence["overall"], "unknown")
        self.assertIn("potential artifact", reasoning["summary"])
        self.assertEqual(uncertainty["qc_artifact"], "high")
        self.assertIn(str(warning), reasoning["uncertainties"])

    def test_composition_evidence_flags_sample_dominance(self) -> None:
        import pandas as pd

        class FakeAdata:
            obs = pd.DataFrame(
                {
                    "cluster": ["0", "0", "0", "0", "1", "1"],
                    "sample": ["s1", "s1", "s1", "s1", "s1", "s2"],
                }
            )

        evidence = {"0": ClusterEvidence("0"), "1": ClusterEvidence("1")}
        _fill_composition_evidence(FakeAdata(), "cluster", evidence, sample_key="sample")

        self.assertEqual(evidence["0"].composition["sample"]["dominant"], "s1")
        self.assertEqual(evidence["0"].composition["sample"]["fraction"], 1.0)
        self.assertTrue(any("sample or batch effect" in warning for warning in evidence["0"].qc_warnings))
        self.assertFalse(evidence["1"].qc_warnings)

    def test_marker_signature_evidence_scores_builtin_sets(self) -> None:
        evidence = {
            "0": ClusterEvidence(
                "0",
                markers=[
                    MarkerGene("CD3D", 8.0, 1.6, 0.001),
                    MarkerGene("CD3E", 7.0, 1.4, 0.001),
                    MarkerGene("TRAC", 6.5, 1.2, 0.001),
                ],
            )
        }

        _fill_marker_signature_evidence(evidence)

        self.assertTrue(evidence["0"].marker_signatures)
        top = evidence["0"].marker_signatures[0]
        self.assertEqual(top["source"], "builtin_marker_signature")
        self.assertIn(top["label"], {"T cell", "CD4 T cell", "CD8 T cell"})
        self.assertGreaterEqual(top["n_matched"], 1)
        self.assertIn("matched_genes", top)

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
            self.assertTrue((output_dir / "evidence_reports" / "provider_reports.json").exists())
            self.assertTrue((output_dir / "evidence_reports" / "marker_based" / "marker_based.qmd").exists())
            self.assertTrue((output_dir / "evidence_reports" / "marker_based" / "marker_based.html").exists())
            self.assertTrue((output_dir / "evidence_reports" / "marker_based" / "marker_based.evidence.json").exists())
            marker_qmd = (output_dir / "evidence_reports" / "marker_based" / "marker_based.qmd").read_text(encoding="utf-8")
            self.assertIn("to_html(index=False", marker_qmd)
            self.assertIn("marker-signature-workspace", marker_qmd)
            self.assertIn("figures/cluster_umap.png", marker_qmd)
            self.assertIn("cluster_signature_tabs.md", marker_qmd)
            self.assertIn("cluster_marker_tabs.md", marker_qmd)
            self.assertIn("Signature scoring uses `scaudit.markers.MARKER_DB`", marker_qmd)
            self.assertTrue((output_dir / "evidence_reports" / "reference_mapping" / "reference_mapping.qmd").exists())
            self.assertTrue((output_dir / "evidence_reports" / "reference_mapping" / "reference_mapping.html").exists())
            self.assertTrue((output_dir / "evidence_reports" / "reference_mapping" / "reference_mapping.evidence.json").exists())
            provider_index = json.loads((output_dir / "evidence_reports" / "provider_reports.json").read_text(encoding="utf-8"))
            provider_ids = {provider["id"] for provider in provider_index["providers"]}
            self.assertTrue({"marker_based", "reference_mapping", "sctype", "sccatch", "scsa"}.issubset(provider_ids))
            for provider_id in ("sctype", "sccatch", "scsa"):
                self.assertTrue((output_dir / "evidence_reports" / provider_id / f"{provider_id}.qmd").exists())
                self.assertTrue((output_dir / "evidence_reports" / provider_id / f"{provider_id}.html").exists())
                self.assertTrue((output_dir / "evidence_reports" / provider_id / f"{provider_id}.evidence.json").exists())
                provider_payload = json.loads(
                    (output_dir / "evidence_reports" / provider_id / f"{provider_id}.evidence.json").read_text(encoding="utf-8")
                )
                self.assertIn(provider_payload["run"]["status"], {"success", "warning"})
            report_html = (output_dir / "report" / "report.html").read_text(encoding="utf-8")
            self.assertIn("Focused evidence reports", report_html)
            self.assertIn("../evidence_reports/marker_based/marker_based.html", report_html)
            self.assertIn("../evidence_reports/reference_mapping/reference_mapping.html", report_html)
            self.assertIn("../evidence_reports/sctype/sctype.html", report_html)
            self.assertIn("../evidence_reports/sccatch/sccatch.html", report_html)
            self.assertIn("../evidence_reports/scsa/scsa.html", report_html)

    def test_marker_provider_writes_standard_json_and_qmd_callouts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            evidence = {
                "0": ClusterEvidence(
                    "0",
                    markers=[
                        MarkerGene("CD3D", 8.0, 1.6, 0.001),
                        MarkerGene("CD3E", 7.0, 1.4, 0.001),
                        MarkerGene("TRAC", 6.5, 1.2, 0.001),
                    ],
                    marker_signatures=[
                        {
                            "source": "builtin_marker_signature",
                            "tool": "scaudit.markers.MARKER_DB",
                            "label": "T cell",
                            "matched_genes": ["CD3D", "CD3E", "TRAC"],
                            "missing_genes": [],
                            "n_matched": 3,
                            "n_signature_genes": 6,
                            "coverage": 0.5,
                            "overlap_score": 0.5,
                        }
                    ],
                )
            }

            payload = write_marker_provider_outputs(temp_path / "input.h5ad", "leiden", temp_path / "marker_based", evidence=evidence)

            self.assertEqual(payload["provider"]["id"], "marker_based")
            self.assertEqual(payload["methods"][0]["tool"], "scanpy.tl.rank_genes_groups")
            evidence_json = json.loads((temp_path / "marker_based" / "marker_based.evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence_json["schema_version"], "0.1.0")
            self.assertTrue((temp_path / "marker_based" / "tables" / "differential_markers.csv").exists())
            self.assertTrue((temp_path / "marker_based" / "cluster_signature_tabs.md").exists())
            self.assertTrue((temp_path / "marker_based" / "cluster_marker_tabs.md").exists())
            callouts = (temp_path / "marker_based" / "callouts.md").read_text(encoding="utf-8")
            self.assertNotIn("callout-note", callouts)
            self.assertNotIn("callout-important", callouts)
            self.assertNotIn("callout-tip", callouts)
            signature_tabs = (temp_path / "marker_based" / "cluster_signature_tabs.md").read_text(encoding="utf-8")
            self.assertIn("## Cluster 0", signature_tabs)
            self.assertNotIn("<th>source</th>", signature_tabs)
            self.assertNotIn("<th>tool</th>", signature_tabs)
            marker_tabs = (temp_path / "marker_based" / "cluster_marker_tabs.md").read_text(encoding="utf-8")
            self.assertIn("## Cluster 0", marker_tabs)
            self.assertIn("<th>Adjusted p-value</th>", marker_tabs)
            self.assertIn("<td>8.00</td>", marker_tabs)
            self.assertIn("<td>1.00e-03</td>", marker_tabs)
            self.assertNotIn("<th></th>", marker_tabs)

    def test_reference_provider_writes_standard_json_and_missing_reference_callout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            evidence = {
                "0": ClusterEvidence(
                    "0",
                    reference_matches=[
                        {"ref_id": "builtin", "label": "T cell", "jaccard": 0.2, "n_shared": 4},
                        {"ref_id": "pbmc_ref", "label": "CD4 T cell", "jaccard": 0.18, "n_shared": 6},
                    ],
                )
            }

            payload = write_reference_provider_outputs(temp_path / "input.h5ad", "leiden", temp_path / "reference_mapping", evidence=evidence)

            self.assertEqual(payload["provider"]["id"], "reference_mapping")
            self.assertEqual(payload["methods"][2]["formula"], "Jaccard(query cluster marker genes, reference label marker genes)")
            self.assertEqual(payload["results"]["summary"]["n_matches"], 1)
            evidence_json = json.loads((temp_path / "reference_mapping" / "reference_mapping.evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence_json["schema_version"], "0.1.0")
            self.assertTrue((temp_path / "reference_mapping" / "tables" / "reference_matches.csv").exists())
            callouts = (temp_path / "reference_mapping" / "callouts.md").read_text(encoding="utf-8")
            self.assertIn("callout-note", callouts)
            self.assertIn("callout-warning", callouts)

    def test_external_annotation_provider_writes_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            evidence = {
                "0": ClusterEvidence(
                    "0",
                    markers=[
                        MarkerGene("CD3D", 8.0, 1.6, 0.001),
                        MarkerGene("CD3E", 7.0, 1.4, 0.001),
                        MarkerGene("TRAC", 6.5, 1.2, 0.001),
                    ],
                )
            }
            payload = write_external_annotation_provider_outputs(
                "sctype", temp_path / "input.h5ad", "leiden", temp_path / "sctype", evidence=evidence
            )

            self.assertEqual(payload["provider"]["id"], "sctype")
            self.assertEqual(payload["run"]["status"], "success")
            self.assertGreater(payload["results"]["summary"]["n_predictions"], 0)
            self.assertTrue((temp_path / "sctype" / "tables" / "provider_status.csv").exists())
            self.assertTrue((temp_path / "sctype" / "tables" / "cluster_predictions.csv").exists())
            status = (temp_path / "sctype" / "tables" / "provider_status.csv").read_text(encoding="utf-8")
            self.assertIn("Computed standardized cluster predictions", status)
            predictions = (temp_path / "sctype" / "tables" / "cluster_predictions.csv").read_text(encoding="utf-8")
            self.assertIn("T cell", predictions)
            self.assertIn("CD3D", predictions)
            callouts = (temp_path / "sctype" / "callouts.md").read_text(encoding="utf-8")
            self.assertIn("callout-note", callouts)
            self.assertIn("callout-warning", callouts)

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

    @unittest.skipIf(importlib.util.find_spec("anndata") is None, "anndata is required for h5ad output test")
    def test_finalize_can_write_annotated_h5ad(self) -> None:
        import anndata as ad
        import numpy as np
        import pandas as pd

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.h5ad"
            adata = ad.AnnData(
                X=np.array(
                    [
                        [2.0, 0.0, 1.0],
                        [2.2, 0.1, 0.9],
                        [0.0, 3.0, 1.0],
                        [0.1, 2.8, 1.1],
                    ]
                ),
                obs=pd.DataFrame({"leiden": ["0", "0", "1", "1"]}, index=[f"cell{i}" for i in range(4)]),
                var=pd.DataFrame(index=["CD3D", "MS4A1", "ACTB"]),
            )
            adata.write_h5ad(input_path)

            config_path = temp_path / "config.toml"
            with redirect_stdout(io.StringIO()):
                main(["init-config", str(input_path), "--out", str(config_path)])
            text = config_path.read_text(encoding="utf-8")
            text = text.replace('cluster_key = ""', 'cluster_key = "leiden"')
            text = text.replace('dir = "results"', f'dir = "{temp_path / "results"}"')
            config_path.write_text(text, encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                main(["run", str(config_path)])

            review_table = temp_path / "results" / "review_table.csv"
            with review_table.open("a", encoding="utf-8") as handle:
                handle.write("0,T cell,Needs review,medium,changed,Reviewed T cell,manual correction\n")

            with redirect_stdout(io.StringIO()):
                main(["review", "import", str(review_table), "--run", str(temp_path / "results")])

            final_dir = temp_path / "final"
            with redirect_stdout(io.StringIO()):
                main(["finalize", str(temp_path / "results"), "--out", str(final_dir), "--write-h5ad"])

            annotated_path = final_dir / "annotated.h5ad"
            self.assertTrue(annotated_path.exists())
            annotated = ad.read_h5ad(annotated_path)
            self.assertIn("scaudit_label", annotated.obs)
            self.assertIn("scaudit_decision", annotated.obs)
            self.assertIn("scaudit_confidence", annotated.obs)
            self.assertIn("scaudit_review_status", annotated.obs)
            self.assertIn("scaudit_label_source", annotated.obs)
            self.assertEqual(annotated.obs.loc["cell0", "scaudit_label"], "Reviewed T cell")
            self.assertEqual(annotated.obs.loc["cell0", "scaudit_label_source"], "reviewed")
            self.assertIn("scaudit", annotated.uns)

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
                            "evidence": {
                                "markers": [
                                    {"gene": "CD3D", "score": 8.2, "log2fc": 1.7, "pval_adj": 0.0001},
                                    {"gene": "NKG7", "score": 5.5, "log2fc": 0.8, "pval_adj": 0.02},
                                ],
                                "marker_signatures": [
                                    {
                                        "source": "builtin_marker_signature",
                                        "tool": "scaudit.markers.MARKER_DB",
                                        "label": "T cell",
                                        "matched_genes": ["CD3D", "NKG7"],
                                        "missing_genes": ["CD3E"],
                                        "n_matched": 2,
                                        "n_signature_genes": 6,
                                        "coverage": 0.333,
                                        "overlap_score": 0.25,
                                    }
                                ],
                                "models": [],
                                "references": [
                                    {"ref_id": "builtin", "label": "T cell", "jaccard": 0.24, "n_shared": 4},
                                    {"ref_id": "pbmc_ref", "label": "CD4 T cell", "jaccard": 0.18, "n_shared": 6}
                                ],
                                "ontology": [],
                                "qc_warnings": [],
                                "qc": {
                                    "pct_counts_mt": {"obs_key": "pct_counts_mt", "mean": 12.5, "median": 10.2},
                                    "n_genes": {"obs_key": "n_genes_by_counts", "mean": 900.0, "median": 850.0},
                                },
                                "composition": {
                                    "sample": {"obs_key": "sample", "dominant": "s1", "dominant_count": 2, "total": 2, "fraction": 1.0}
                                },
                            },
                            "reasoning": {
                                "summary": "review",
                                "summary_source": "llm",
                                "summary_model": "gpt-5.2",
                                "supports": [],
                                "contradictions": [],
                                "uncertainties": [],
                                "validation_suggestions": [],
                            },
                            "provenance": {"cell_count": 2},
                        },
                        {
                            "cluster_id": "1",
                            "proposed_label": "pending",
                            "decision": "Needs review",
                            "confidence": {"overall": "unknown", "lineage": "unknown", "subtype": "unknown"},
                            "evidence": {"markers": [], "models": [], "references": [], "ontology": [], "qc_warnings": [], "qc": {}},
                            "reasoning": {"summary": "missing evidence", "supports": [], "contradictions": [], "uncertainties": [], "validation_suggestions": []},
                            "provenance": {"cell_count": 1},
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
            self.assertIn("https://github.com/chaochungkuo/scaudit", html)
            self.assertIn('class="logo-mark"', html)
            self.assertIn('class="github-mark"', html)
            self.assertIn('aria-label="Open scaudit on GitHub"', html)
            self.assertIn("LLM-generated", html)
            self.assertIn("Generated by LLM model gpt-5.2", html)
            self.assertIn("Evidence stack", html)
            self.assertIn("Marker-based evidence", html)
            self.assertIn("Scanpy rank_genes_groups", html)
            self.assertIn("built-in marker signature scoring", html)
            self.assertIn("signature coverage/overlap", html)
            self.assertIn("Marker rule", html)
            self.assertIn("1 strong, 1 moderate, 0 weak", html)
            self.assertIn("CD3D (log2FC +1.70, padj 1.0e-04, score 8.20, strong)", html)
            self.assertIn("Signature scoring", html)
            self.assertIn("T cell (coverage 33%; overlap 0.25; matched: CD3D, NKG7)", html)
            self.assertIn("Marker-set overlap", html)
            self.assertIn("T cell (0.24), 4 shared genes", html)
            self.assertIn("Reference-based mapping", html)
            self.assertIn("Model-based prediction", html)
            self.assertIn("Ontology reasoning", html)
            self.assertIn("Planned Cell Ontology layer", html)
            self.assertIn("LLM explanation", html)
            self.assertIn("explanation-only", html)
            self.assertIn("QC and artifact evidence", html)
            self.assertIn("Evidence completeness", html)
            self.assertIn("0/2 clusters have all evidence sources", html)
            self.assertIn(">OK</span>", html)
            self.assertIn(">NA</span>", html)
            self.assertIn("Reference match matrix", html)
            self.assertIn("window.scauditReferenceHeatmap", html)
            self.assertIn("pbmc_ref:CD4 T cell", html)
            self.assertIn("Jaccard: 0.180", html)
            self.assertIn("Marker expression evidence", html)
            self.assertIn("Marker expression", html)
            self.assertIn("window.scauditMarkerHeatmap", html)
            self.assertIn("colorscale", html)
            self.assertIn("QC metrics", html)
            self.assertIn("mito % median 10.2", html)
            self.assertIn("Composition", html)
            self.assertIn("sample s1 100%", html)
            self.assertIn("CD3D", html)
            self.assertIn("log2FC: +1.70", html)
            self.assertIn("window.scauditUMAPTraces", html)

    def test_debug_command_prints_cluster_evidence_panel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            run_dir = temp_path / "results"
            run_dir.mkdir()
            (run_dir / "annotation_cards.json").write_text(
                json.dumps(
                    [
                        {
                            "cluster_id": "0",
                            "proposed_label": "T cell",
                            "decision": "Needs review",
                            "confidence": {"overall": "medium", "lineage": "medium", "subtype": "unknown"},
                            "evidence": {
                                "markers": [{"gene": "CD3D", "score": 8.2, "log2fc": 1.7, "pval_adj": 0.0001}],
                                "models": [{"model": "CellTypist", "label": "T cell", "probability": 0.82}],
                                "references": [{"ref_id": "pbmc_ref", "label": "CD4 T cell", "jaccard": 0.18, "n_shared": 6}],
                                "qc": {"pct_counts_mt": {"obs_key": "pct_counts_mt", "mean": 8.0, "median": 7.0}},
                                "composition": {
                                    "sample": {"obs_key": "sample", "dominant": "s1", "dominant_count": 9, "total": 10, "fraction": 0.9}
                                },
                                "qc_warnings": [],
                            },
                            "reasoning": {
                                "summary": "Cluster 0 has T cell evidence.",
                                "supports": ["CD3D supports T cell identity"],
                                "contradictions": [],
                                "uncertainties": [],
                                "validation_suggestions": [],
                            },
                            "uncertainty": {"marker_inconsistency": "medium"},
                            "provenance": {"cell_count": 10},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                main(["debug", "--run", str(run_dir), "--cluster", "0"])

            text = output.getvalue()
            self.assertIn("Cluster 0 debug", text)
            self.assertIn("Decision path", text)
            self.assertIn("Top markers", text)
            self.assertIn("CD3D", text)
            self.assertIn("Model evidence", text)
            self.assertIn("Reference evidence", text)
            self.assertIn("QC evidence", text)
            self.assertIn("Composition evidence", text)
            self.assertIn("s1", text)
            self.assertIn("Reasoning", text)

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
        self.assertEqual(cards[0]["reasoning"]["summary_source"], "llm")
        self.assertEqual(cards[0]["reasoning"]["summary_provider"], "openai")
        self.assertEqual(cards[0]["reasoning"]["summary_model"], "model")
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

    def test_reference_search_lists_public_candidates(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            main(["reference", "search", "--species", "mouse", "--tissue", "heart"])

        text = output.getvalue()
        self.assertIn("Public reference candidates", text)
        self.assertIn("tabula_muris_heart", text)
        self.assertIn("Tabula Muris", text)

    def test_reference_recommend_can_write_config_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.toml"
            with redirect_stdout(io.StringIO()):
                main(["init-config", "input.h5ad", "--out", str(config_path)])
            text = config_path.read_text(encoding="utf-8")
            text = text.replace('species = ""', 'species = "mouse"')
            text = text.replace('tissue = ""', 'tissue = "heart"')
            config_path.write_text(text, encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                main(["reference", "recommend", "--config", str(config_path), "--write"])

            self.assertIn("Recommended references", output.getvalue())
            self.assertIn("tabula_muris_heart", output.getvalue())
            self.assertIn('selected = ["tabula_muris_heart"]', config_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
