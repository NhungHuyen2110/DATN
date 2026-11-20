"""Run maintained modular checks without importing eager legacy service clients.

Legacy test_price_intent is intentionally not silently rewritten or mocked here;
its external-runtime requirement is documented in the acceptance report.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"AI/tests"), str(ROOT/"AI")]
MODULES = ("test_api_contract", "test_model_policy", "test_modular_pipeline", "test_csv_ingestion",
           "test_entity_linking", "test_evaluation", "test_review_workflow", "test_storage_integration")

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in MODULES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
