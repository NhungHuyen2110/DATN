"""Execute actual health function bodies without business router import side effects."""
import ast
import logging
from pathlib import Path
import unittest
from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


class DeploymentHealthTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'app/main.py').read_text(encoding='utf-8-sig'))
        self.check = Mock(return_value=True)
        app = FastAPI()
        namespace = {'app': app, 'check_database': self.check, 'HTTPException': HTTPException,
                     'logger': logging.getLogger('health-test')}
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {'health', 'liveness', 'readiness'}]
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<health-routes>', 'exec'), namespace)
        self.client = TestClient(app)

    def test_liveness_survives_database_outage_and_readiness_fails_safely(self):
        self.check.side_effect = ConnectionError('synthetic-secret-do-not-expose')
        self.assertEqual(self.client.get('/health/live').status_code, 200)
        self.check.assert_not_called()
        response = self.client.get('/health/ready')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('synthetic-secret', response.text)

    def test_existing_and_new_readiness_routes_preserve_healthy_contract(self):
        legacy = self.client.get('/health')
        current = self.client.get('/health/ready')
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json(), legacy.json())
