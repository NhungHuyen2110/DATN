"""Policy tests do not import or download a real model."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lumiere.bootstrap import SemanticModelProvider


class ModelPolicyTests(unittest.TestCase):
    def test_default_only_uses_local_files_and_reuses_loaded_model(self):
        factory = Mock()
        with patch.dict(sys.modules,{"sentence_transformers":SimpleNamespace(SentenceTransformer=factory)}), \
             patch.dict(os.environ,{"AI_ALLOW_MODEL_DOWNLOAD":"false","AI_MODEL_CACHE":"existing-cache"}):
            provider = SemanticModelProvider()
            self.assertIs(provider.get(),provider.get())
        factory.assert_called_once()
        self.assertTrue(factory.call_args.kwargs["local_files_only"])
        self.assertFalse(factory.call_args.kwargs["trust_remote_code"])
        self.assertEqual(factory.call_args.kwargs["cache_folder"],"existing-cache")

    def test_download_requires_explicit_opt_in(self):
        factory = Mock()
        with patch.dict(sys.modules,{"sentence_transformers":SimpleNamespace(SentenceTransformer=factory)}), \
             patch.dict(os.environ,{"AI_ALLOW_MODEL_DOWNLOAD":"true"}):
            SemanticModelProvider().get()
        self.assertFalse(factory.call_args.kwargs["local_files_only"])
