"""Real image decoding/storage and cookie authorization, isolated SQLite and temp files."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
import test_orders_api as fixtures


class ProductImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = type('ImageFixture', (fixtures.OrderTests,), {})
        cls.seed.setUpClass()
        cls.addClassCleanup(cls.seed.tearDownClass)

    def setUp(self):
        fixture = self.seed('test_checkout_snapshots_stock_and_cart_atomic')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        setting = patch.dict('os.environ', {'LUMIERE_PRODUCT_IMAGE_DIR': str(self.root)})
        setting.start(); self.addCleanup(setting.stop)
        self.client = TestClient(fixture.app)
        self.addCleanup(self.client.close)

    @staticmethod
    def png(color='red'):
        output = BytesIO()
        Image.new('RGB', (12, 8), color).save(output, format='PNG')
        return output.getvalue()

    def upload(self, content=None, token='admin-token', ident=1, mime='image/png'):
        headers = {'Content-Type': mime}
        if token:
            headers['Cookie'] = 'lumiere_session=' + token
        return self.client.post(f'/admin/products/{ident}/image',
            content=self.png() if content is None else content, headers=headers)

    def test_product_image_upload_normalizes_and_is_publicly_visible(self):
        self.assertNotIn('image_url', self.client.get('/products/1').json())
        result = self.upload()
        self.assertEqual(result.status_code, 200, result.text)
        url = result.json()['image_url']
        self.assertEqual(self.client.get('/products/1').json()['image_url'], url)
        image = self.client.get(url)
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers['content-type'], 'image/webp')
        with Image.open(BytesIO(image.content)) as decoded:
            self.assertEqual(decoded.size, (12, 8))
            self.assertNotIn('exif', decoded.info)

    def test_product_image_requires_admin_and_existing_product(self):
        for token, status in [(None, 401), ('test-token', 403), ('staff-token', 403)]:
            with self.subTest(token=token):
                self.assertEqual(self.upload(token=token).status_code, status)
        self.assertEqual(self.upload(ident=999).status_code, 404)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_product_image_rejects_corruption_svg_and_oversize_without_overwrite(self):
        self.assertEqual(self.upload().status_code, 200)
        original = (self.root / '1/cover.webp').read_bytes()
        for content, mime, status in [(b'not a PNG', 'image/png', 422),
                (b'<svg onload="alert(1)"></svg>', 'image/svg+xml', 415),
                (b'x' * (5 * 1024 * 1024 + 1), 'image/png', 413)]:
            with self.subTest(status=status):
                self.assertEqual(self.upload(content, mime=mime).status_code, status)
                self.assertEqual((self.root / '1/cover.webp').read_bytes(), original)

    def test_product_image_replacement_retains_previous_cover(self):
        self.assertEqual(self.upload().status_code, 200)
        original = (self.root / '1/cover.webp').read_bytes()
        self.assertEqual(self.upload(self.png('blue')).status_code, 200)
        self.assertNotEqual((self.root / '1/cover.webp').read_bytes(), original)
        self.assertIn(original, [p.read_bytes() for p in (self.root / '1/history').iterdir()])

    def test_product_image_unavailable_storage_is_controlled_and_catalog_survives(self):
        with patch('app.services.product_images.save_cover', side_effect=OSError('private path')):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private path', response.text)
        with patch('pathlib.Path.stat', side_effect=PermissionError('private path')):
            response = self.client.get('/products/1')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('image_url', response.json())
