import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('changed_services', Path(__file__).resolve().parents[2] / 'scripts/changed_services.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ChangedServiceTests(unittest.TestCase):
    def names(self, paths):
        return {item['service'] for item in module.plan(paths)['include']}

    def test_ai_change_does_not_rebuild_frontend_or_business(self):
        self.assertEqual(self.names(['AI/jewelry_agents/search_service.py']), {'AI', 'index-worker'})
        self.assertEqual(self.names(['frontend/index.html']), {'frontend'})
        self.assertEqual(self.names(['backend/app/main.py']), {'backend', 'index-worker'})

    def test_shared_library_and_global_context_invalidate_dependent_images(self):
        self.assertEqual(self.names(['shared/observability.py']), {'AI', 'backend', 'index-worker'})
        self.assertEqual(self.names(['docs/09-evaluation.md']), set())
        self.assertEqual(len(module.plan([], all_services=True)['include']), 4)
        for item in module.plan([], all_services=True)['include']:
            self.assertEqual(item['image'], item['image'].lower())
