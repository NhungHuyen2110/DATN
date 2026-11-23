import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/prepare_dialogue_model_cache.py'
spec = importlib.util.spec_from_file_location('dialogue_cache_qa', SCRIPT)
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class DialogueCacheSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source, self.target = (Path(self.directory.name) / p for p in ('source', 'target'))
        self.source.mkdir()
        self.target.mkdir()
        self.manifest = {'config': self.blob(b'{"architecture":"qa-only"}'),
                         'layers': [self.blob(b'synthetic-model-bytes' * 10)]}
        self.manifest_path = self.source / cache.MANIFEST
        self.manifest_path.parent.mkdir(parents=True)
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        for name, value in [('SOURCE', self.source), ('TARGET', self.target)]:
            patcher = patch.object(cache, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def blob(self, data):
        digest = hashlib.sha256(data).hexdigest()
        path = self.source / 'blobs' / ('sha256-' + digest)
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return {'digest': 'sha256:' + digest, 'size': len(data)}

    def run_copy(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            cache.main()
        return json.loads(stream.getvalue())

    def test_replay_preserves_source_and_reuses_hash_verified_blobs(self):
        before = {str(p.relative_to(self.source)): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        first, second = self.run_copy(), self.run_copy()
        self.assertEqual((first['blobs_copied'], second['blobs_reused']), (2, 2))
        self.assertEqual(second['blobs_copied'], 0)
        after = {str(p.relative_to(self.source)): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual((self.target / cache.MANIFEST).read_bytes(), self.manifest_path.read_bytes())

    def test_corrupt_source_is_not_published_as_a_usable_model(self):
        blob = self.manifest['layers'][0]
        source = self.source / 'blobs' / blob['digest'].replace(':', '-')
        source.write_bytes(b'x' * blob['size'])
        with self.assertRaises(ValueError):
            self.run_copy()
        self.assertFalse((self.target / cache.MANIFEST).exists())
        self.assertEqual(source.read_bytes(), b'x' * blob['size'])

    def test_existing_different_blob_is_never_overwritten(self):
        blob = self.manifest['config']
        target = self.target / 'blobs' / blob['digest'].replace(':', '-')
        target.parent.mkdir()
        target.write_bytes(b'existing evidence')
        with self.assertRaises(ValueError):
            self.run_copy()
        self.assertEqual(target.read_bytes(), b'existing evidence')
        self.assertFalse((self.target / cache.MANIFEST).exists())

    def test_manifest_cannot_choose_a_path_outside_the_cache(self):
        self.manifest['config']['digest'] = '../../outside'
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.run_copy()
        self.assertEqual(list(self.target.iterdir()), [])
