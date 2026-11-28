"""Offline AI contract tests: real Qdrant local, no model/server/LLM calls."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='Create new test result JSON')
    parser.add_argument('--pattern', default='test_*.py', help='Test filename glob; the same offline guards always apply')
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error('Report already exists')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / 'AI'))
    sys.path.insert(0, str(ROOT))
    model_module = ModuleType('sentence_transformers')
    model_module.SentenceTransformer = MagicMock(side_effect=AssertionError('Model use forbidden in offline contract tests'))
    env = {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
           'LUMIERE_ALLOW_ISOLATED_GRAPH_TEST': '0', 'LUMIERE_RETRIEVAL_V2_ENABLED': 'true'}
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, env))
        stack.enter_context(patch.dict(sys.modules, {'sentence_transformers': model_module}))
        stack.enter_context(patch('dotenv.load_dotenv', return_value=False))
        stack.enter_context(patch('neo4j.GraphDatabase.driver', side_effect=AssertionError('Live graph forbidden')))
        stack.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('HTTP network forbidden')))
        stack.enter_context(patch('httpx.HTTPTransport.handle_request', side_effect=AssertionError('HTTP network forbidden')))
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'AI/tests'), pattern=args.pattern)
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'pattern': args.pattern,
              'skipped': len(result.skipped), 'successful': result.wasSuccessful(),
              'graph_integration': 'not_run_requires_isolated_server',
              'qdrant': 'actual_in_memory_engine_with_synthetic_vectors',
              'real_model_quality': 'not_evaluated'}
    if args.report:
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
            handle.write('\n')
    print(json.dumps(report))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
