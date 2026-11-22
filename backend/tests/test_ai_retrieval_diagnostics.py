from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.core.database import get_db
from app.routers.auth import get_current_user
from app.routers.ai_admin import router
from app.services.ai_retrieval_diagnostics import retrieval_diagnostics


class RetrievalDiagnosticsRoleTests(unittest.TestCase):
    def test_only_admin_reaches_internal_service(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: object()
        client = TestClient(app)
        payload = {'query': 'Top 3 nhẫn', 'top_k': 3}
        with patch('app.services.ai_retrieval_diagnostics.retrieval_diagnostics', return_value={'products': []}) as service:
            self.assertEqual(client.post('/admin/ai/retrieval-diagnostics', json=payload).status_code, 401)
            for role in ('customer', 'staff'):
                app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(role=SimpleNamespace(name=role))
                self.assertEqual(client.post('/admin/ai/retrieval-diagnostics', json=payload).status_code, 403)
            service.assert_not_called()
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=SimpleNamespace(name='admin'))
            self.assertEqual(client.post('/admin/ai/retrieval-diagnostics', json=payload).status_code, 200)
            self.assertEqual(client.post('/admin/ai/retrieval-diagnostics', json={**payload, 'top_k': 100}).status_code, 422)

    def test_disabled_service_makes_no_network_call(self):
        with patch.dict('os.environ', {'LUMIERE_AI_DIAGNOSTICS_TOKEN': ''}), patch('requests.post') as post:
            with self.assertRaises(HTTPException) as caught:
                retrieval_diagnostics({'query': 'nhẫn'})
            self.assertEqual(caught.exception.status_code, 503)
            post.assert_not_called()

    def test_only_catalog_fields_are_relayed_and_browser_credentials_are_not_forwarded(self):
        response = Mock()
        response.json.return_value = {'status': 'ok', 'products': [{'ProductID': 1, 'score': .01,
            'cost_price': 'SECRET', 'user_email': 'private@example.com'}], 'server_token': 'SECRET'}
        with patch.dict('os.environ', {'LUMIERE_AI_DIAGNOSTICS_TOKEN': 'synthetic-token'}), \
                patch('requests.post', return_value=response) as post:
            result = retrieval_diagnostics({'query': 'nhẫn', 'top_k': 1})
        self.assertNotIn('cost_price', result['products'][0])
        self.assertNotIn('user_email', result['products'][0])
        self.assertNotIn('server_token', result)
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer synthetic-token')
        self.assertEqual(post.call_args.kwargs['timeout'], 15)
