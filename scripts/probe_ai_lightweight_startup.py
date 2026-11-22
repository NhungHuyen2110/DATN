"""Prove a cold source AI import needs no transformer package/model/driver connection."""
from pathlib import Path
import json
import os
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'AI')]
os.environ.update({'LUMIERE_DENSE_ENABLED': 'false', 'LUMIERE_GRAPH_ENABLED': 'false'})
with patch.dict(sys.modules, {'sentence_transformers': None}), patch('dotenv.load_dotenv', return_value=False), \
        patch('qdrant_client.QdrantClient', side_effect=AssertionError('No Qdrant constructor')), \
        patch('neo4j.GraphDatabase.driver', side_effect=AssertionError('No graph constructor')), \
        patch('requests.sessions.Session.request', side_effect=AssertionError('No HTTP calls')):
    import api
    assert api.app.title
print(json.dumps({'cold_source_import': 'passed', 'transformer_package_available': False,
                  'model_constructed': False, 'database_or_network_access': False}))
