"""Validate callback paths without real merchant settings or gateway access."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.services.payment_providers import VNPaySandbox


class CallbackConfigTests(unittest.TestCase):
    def test_sandbox_return_accepts_direct_and_proxy_paths(self):
        for path in ('/payments/vnpay/return', '/api/payments/vnpay/return'):
            values={'VNPAY_ENABLED':'true','VNPAY_TMN_CODE':'TESTONLY',
                    'VNPAY_HASH_SECRET':'unit-test-placeholder', 'VNPAY_RETURN_URL':'https://example.invalid'+path}
            with self.subTest(path=path), patch.dict('os.environ', values):
                self.assertEqual(VNPaySandbox.from_environment().return_url, values['VNPAY_RETURN_URL'])

    def test_sandbox_return_keeps_https_and_credentials_protection(self):
        for url in ('http://example.invalid/api/payments/vnpay/return',
                    'https://user:password@example.invalid/api/payments/vnpay/return',
                    'https://example.invalid/other', 'https://example.invalid/payments/vnpay/return?x=1'):
            values={'VNPAY_ENABLED':'true','VNPAY_TMN_CODE':'TESTONLY',
                    'VNPAY_HASH_SECRET':'unit-test-placeholder','VNPAY_RETURN_URL':url}
            with self.subTest(url=url), patch.dict('os.environ', values):
                with self.assertRaises(HTTPException):
                    VNPaySandbox.from_environment()
