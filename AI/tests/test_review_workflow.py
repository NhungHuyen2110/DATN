"""Synthetic unit examples verify review gates, never measure model quality."""
import csv
from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumiere.review_data import entity_metrics, load_reviewed_cases
from lumiere.label_review import export_reviewed_labels
import evaluate_retrieval

ROOT = Path(__file__).resolve().parents[2]


class ReviewWorkflowTests(unittest.TestCase):
    def test_all_generated_candidates_are_pending_and_not_scored(self):
        source = ROOT / "docs/review/benchmark-candidates.csv"
        cases, counts = load_reviewed_cases(source)
        self.assertEqual(cases, [])
        self.assertGreaterEqual(counts["pending_review"], 100)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"report.json"
            self.assertEqual(evaluate_retrieval.main(["--dataset",str(source),"--output",str(output)]), 2)
            self.assertIsNone(json.loads(output.read_text(encoding="utf-8"))["summary"])

    def test_approval_without_reviewer_or_answers_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/"cases.jsonl"
            row = {"query_id":"test", "query":"SKU", "review_status":"APPROVED", "expected_intent":"product_search", "expected_entities":{}, "hard_constraints":{}}
            source.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_reviewed_cases(source)
            row["reviewer"] = "unit-test-only"
            source.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_reviewed_cases(source)

    def test_entity_accuracy_requires_exact_canonical_set(self):
        self.assertEqual(entity_metrics({"audience":["female"]},{"audience":["female"]})["entity_linking_accuracy"],1)
        result = entity_metrics({"audience":["female"]},{"audience":["female_child"]})
        self.assertEqual(result["entity_linking_accuracy"],0)
        self.assertEqual(result["entity_f1"],0)

    def test_reviewed_test_fixture_runs_real_lexical_evaluator(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"cases.jsonl", Path(directory)/"results.json"
            source.write_text(json.dumps({"query_id":"unit-only", "query":"SP000001", "top_k":1,
                "expected_intent":"product_search", "expected_entities":{}, "expected_product_ids":[1], "hard_constraints":{},
                "review_status":"APPROVED", "reviewer":"UNIT_FIXTURE_NOT_A_HUMAN_BENCHMARK"}), encoding="utf-8")
            with patch.dict("os.environ", {"AI_CATALOG_SOURCE":"csv", "AI_CATALOG_PATH":str(ROOT/"output/products_ai.csv")}), redirect_stdout(io.StringIO()):
                self.assertEqual(evaluate_retrieval.main(["--dataset",str(source),"--output",str(output),"--mode","lexical"]),0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["precision_at_k"],1)
            self.assertFalse(result["sufficient_100_reviewed"])

    def test_pending_labels_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"approved.csv"
            result = export_reviewed_labels(ROOT/"output/products_ai.csv", ROOT/"docs/review/product-label-review.csv",target)
            self.assertEqual(result["status"], "PENDING_REVIEW")
            self.assertFalse(target.exists())

    def test_explicit_human_annotation_provenance_and_stale_source_guard(self):
        source = ROOT/"AI/tests/fixtures/catalog_semantic.csv"
        row = {"product_id":900101,"sku":"TEST-N001", "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
               "candidate_audience":"female", "audience_evidence":"UNIT FIXTURE annotation",
               "audience_evidence_field":"human_review", "audience_confidence":"1",
               "review_status":"APPROVED", "reviewer":"UNIT_TEST_ONLY", "review_notes":"Synthetic test annotation"}
        with tempfile.TemporaryDirectory() as directory:
            review, target = Path(directory)/"review.csv", Path(directory)/"output.csv"
            def write():
                with review.open("w",encoding="utf-8",newline="") as f:
                    writer=csv.DictWriter(f,row.keys()); writer.writeheader(); writer.writerow(row)
            write()
            self.assertEqual(export_reviewed_labels(source,review,target)["exported_facts"],1)
            self.assertIn("review_sha256",target.read_text(encoding="utf-8-sig"))
            row["source_sha256"]="stale"
            write()
            with self.assertRaises(ValueError):
                export_reviewed_labels(source,review,Path(directory)/"stale.csv")
