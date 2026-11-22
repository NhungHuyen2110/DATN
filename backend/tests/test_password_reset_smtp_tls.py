import ssl
import unittest
from unittest.mock import MagicMock, patch

from app.routers.password_reset import _send_email


class SMTPResetSecurityTests(unittest.TestCase):
    settings = {'SMTP_HOST':'smtp.example.com', 'SMTP_USER':'demo@example.com',
                'SMTP_PASSWORD':'synthetic-only-smtp-password', 'SMTP_FROM':'demo@example.com'}

    def test_smtp_verifies_certificate_and_hostname_before_login(self):
        client = MagicMock()
        with patch.dict('os.environ', self.settings), patch('smtplib.SMTP') as smtp:
            smtp.return_value.__enter__.return_value = client
            self.assertTrue(_send_email('recipient@example.com', 'https://example.com/reset-password?token=test-only'))
        context = client.starttls.call_args.kwargs['context']
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        client.login.assert_called_once()
        client.send_message.assert_called_once()

    def test_certificate_failure_never_sends_password_or_message(self):
        client = MagicMock()
        client.starttls.side_effect = ssl.SSLCertVerificationError('synthetic certificate rejection')
        with patch.dict('os.environ', self.settings), patch('smtplib.SMTP') as smtp:
            smtp.return_value.__enter__.return_value = client
            with self.assertRaises(ssl.SSLCertVerificationError):
                _send_email('recipient@example.com', 'https://example.com/reset-password?token=test-only')
        client.login.assert_not_called()
        client.send_message.assert_not_called()
