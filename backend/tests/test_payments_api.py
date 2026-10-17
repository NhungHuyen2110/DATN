"""Mock merchant settings only; no VNPay network or real PostgreSQL access."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_orders_api as orders_tests


class PaymentTests(orders_tests.OrderTests):
    def setUp(self):
        super().setUp()
        from app.models import PaymentTransaction
        from app.services.payment_providers import VNPaySandbox
        self.Payment = PaymentTransaction
        # Pure test fixtures, never environment credentials or real merchant data.
        self.provider = VNPaySandbox("TESTONLY", "unit-test-hmac-key-not-merchant-credentials", "https://example.com/payments/vnpay/return")
        for target in ("app.services.payment_providers.get_provider", "app.services.payments.get_provider"):
            mocked = patch(target, return_value=self.provider)
            mocked.start()
            self.addCleanup(mocked.stop)

    def online_order(self):
        self.add()
        body = self.shipping()
        body["payment_method"] = "vnpay"
        status, order, _ = self.checkout(body)
        self.assertEqual(status, 201)
        status, result, _ = self.cart_call("POST", f"/orders/{order['id']}/payments/vnpay")
        self.assertEqual(status, 200)
        return order, result

    def callback_params(self, result, **changes):
        query = {key: values[0] for key, values in parse_qs(urlsplit(result["payment_url"]).query).items()}
        params = {
            "vnp_TxnRef": query["vnp_TxnRef"], "vnp_TmnCode": query["vnp_TmnCode"],
            "vnp_Amount": query["vnp_Amount"], "vnp_OrderInfo": query["vnp_OrderInfo"],
            "vnp_ResponseCode": "00", "vnp_TransactionStatus": "00", "vnp_TransactionNo": "123456",
            "vnp_PayDate": query["vnp_CreateDate"], "vnp_BankCode": "NCB",
        }
        params.update(changes)
        params["vnp_SecureHash"] = self.provider.sign(params)
        return params

    def callback(self, params, return_url=False):
        query = urlencode(params, doseq=True).encode()

        async def wrapped(scope, receive, send):
            scope["query_string"] = query
            await self.app(scope, receive, send)

        path = "/payments/vnpay/return" if return_url else "/payments/vnpay/ipn"
        return asyncio.run(orders_tests.cart_tests.profile.request(wrapped, "GET", path))

    def payment(self, ident):
        with Session(self.engine) as db:
            table = self.Payment.__table__
            return dict(db.execute(sa.select(table).where(table.c.id == ident)).mappings().one())

    def test_cod_confirmation_requires_admin_delivered_and_receipt(self):
        self.add()
        order = self.checkout()[1]
        self.assertEqual(order["payment_method"], "cod")
        self.assertEqual(order["payment_status"], "unpaid")
        path = f"/admin/orders/{order['id']}/cod/confirm"
        body = {"collection_reference": "TEST-RECEIPT-001"}
        self.assertEqual(self.cart_call("POST", path, body)[0], 403)
        self.assertEqual(self.admin_call("POST", path, body, staff=True)[0], 403)
        self.assertEqual(self.admin_call("POST", path, body)[0], 409)
        for status in ("confirmed", "packing", "shipping", "delivered"):
            self.status(order["id"], status)
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "unpaid")
        status, result, _ = self.admin_call("POST", path, body)
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(self.admin_call("POST", path, body)[1]["id"], result["id"])
        self.assertEqual(self.admin_call("POST", path, {"collection_reference": "different"})[0], 409)
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "paid")
        self.assertEqual(self.stock(), 4)

    def test_vnpay_url_canonical_hmac_and_idempotent_creation(self):
        order, result = self.online_order()
        parsed = urlsplit(result["payment_url"])
        self.assertEqual(parsed.netloc, "sandbox.vnpayment.vn")
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        signature = params.pop("vnp_SecureHash")
        encoded = urlencode(sorted(params.items()))
        expected = hmac.new(self.provider.secret.encode(), encoded.encode(), hashlib.sha512).hexdigest()
        self.assertEqual(signature, expected)
        self.assertEqual(params["vnp_Amount"], str(int(Decimal(order["total_vnd"]) * 100)))
        self.assertEqual(params["vnp_Version"], "2.1.0")
        second = self.cart_call("POST", f"/orders/{order['id']}/payments/vnpay")[1]
        self.assertEqual(second, result)
        self.assertNotIn(self.provider.secret, json.dumps(result))
        from app.services.payment_providers import canonical
        self.assertEqual(canonical({"b": "/", "a": "hello world"}), "a=hello+world&b=%2F")

    def test_return_is_read_only_even_if_correctly_signed(self):
        order, result = self.online_order()
        status, body, _ = self.callback(self.callback_params(result), return_url=True)
        self.assertEqual(status, 200)
        self.assertEqual(body["payment_status"], "unpaid")
        self.assertEqual(self.payment(result["transaction"]["id"])["status"], "pending")
        self.assertEqual(self.stock(), 4)

    def test_ipn_success_duplicate_and_no_inventory_change(self):
        order, result = self.online_order()
        params = self.callback_params(result)
        self.assertEqual(self.callback(params)[1]["RspCode"], "00")
        self.assertEqual(self.callback(params)[1]["RspCode"], "02")
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "paid")
        self.assertEqual(self.payment(result["transaction"]["id"])["status"], "succeeded")
        self.assertEqual(self.stock(), 4)
        self.assertEqual(self.status(order["id"], "cancelled")[0], 409)

    def test_tampered_signature_duplicate_params_and_merchant(self):
        _, result = self.online_order()
        params = self.callback_params(result)
        params["vnp_Amount"] = "1"
        self.assertEqual(self.callback(params)[1]["RspCode"], "97")
        params = self.callback_params(result)
        params["vnp_TxnRef"] = [params["vnp_TxnRef"], "evil"]
        self.assertEqual(self.callback(params)[1]["RspCode"], "97")
        self.assertEqual(self.callback(self.callback_params(result, vnp_TmnCode="WRONGONE"))[1]["RspCode"], "97")
        self.assertEqual(self.payment(result["transaction"]["id"])["status"], "pending")

    def test_signed_wrong_amount_reference_and_order(self):
        _, result = self.online_order()
        for changes, code in (({"vnp_Amount": "100"}, "04"), ({"vnp_TxnRef": "unknown"}, "01"), ({"vnp_OrderInfo": "other order"}, "01")):
            self.assertEqual(self.callback(self.callback_params(result, **changes))[1]["RspCode"], code)
        self.assertEqual(self.payment(result["transaction"]["id"])["status"], "pending")

    def test_failed_payment_does_not_restore_stock_until_admin_cancel(self):
        order, result = self.online_order()
        params = self.callback_params(result, vnp_ResponseCode="24", vnp_TransactionStatus="02", vnp_TransactionNo="0")
        self.assertEqual(self.callback(params)[1]["RspCode"], "00")
        self.assertEqual(self.payment(result["transaction"]["id"])["status"], "failed")
        self.assertEqual(self.stock(), 4)
        self.assertEqual(self.status(order["id"], "cancelled")[0], 200)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.status(order["id"], "cancelled")[0], 200)
        self.assertEqual(self.stock(), 5)

    def test_pending_unknown_or_locally_expired_cannot_cancel_or_retry(self):
        order, result = self.online_order()
        self.assertEqual(self.status(order["id"], "cancelled")[0], 409)
        params = self.callback_params(result, vnp_ResponseCode="99", vnp_TransactionStatus="07")
        self.callback(params)
        self.assertTrue(self.payment(result["transaction"]["id"])["review_required"])
        with Session(self.engine) as db, db.begin():
            db.get(self.Payment, result["transaction"]["id"]).expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.assertEqual(self.status(order["id"], "cancelled")[0], 409)
        self.assertEqual(self.cart_call("POST", f"/orders/{order['id']}/payments/vnpay")[0], 409)
        self.assertEqual(self.stock(), 4)

    def test_success_pay_date_or_bank_reference_invalid_requires_review(self):
        _, result = self.online_order()
        self.callback(self.callback_params(result, vnp_PayDate="20000101000000"))
        payment = self.payment(result["transaction"]["id"])
        self.assertTrue(payment["review_required"])
        self.assertEqual(payment["status"], "pending")
        self.callback(self.callback_params(result, vnp_TransactionNo="0"))
        self.assertEqual(self.payment(payment["id"])["status"], "pending")

    def test_conflicting_late_success_after_cancel_is_flagged_not_paid(self):
        order, result = self.online_order()
        self.callback(self.callback_params(result, vnp_ResponseCode="11", vnp_TransactionStatus="02", vnp_TransactionNo="0"))
        self.status(order["id"], "cancelled")
        self.assertEqual(self.callback(self.callback_params(result))[1]["RspCode"], "02")
        payment = self.payment(result["transaction"]["id"])
        self.assertTrue(payment["review_required"])
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "unpaid")

    def test_callback_commit_failure_rolls_back_and_gateway_can_retry(self):
        order, result = self.online_order()
        params = self.callback_params(result)
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-error")):
            self.assertEqual(self.callback(params)[1]["RspCode"], "99")
        self.assertEqual(self.payment(result["transaction"]["id"])["status"], "pending")
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "unpaid")
        self.assertEqual(self.callback(params)[1]["RspCode"], "00")

    def test_gateway_transaction_cannot_pay_two_orders(self):
        first_order, first = self.online_order()
        second_order, second = self.online_order()
        self.assertEqual(self.callback(self.callback_params(first))[1]["RspCode"], "00")
        self.assertEqual(self.callback(self.callback_params(second))[1]["RspCode"], "99")
        self.assertEqual(self.cart_call(path=f"/orders/{second_order['id']}")[1]["payment_status"], "unpaid")
        self.assertEqual(self.payment(second["transaction"]["id"])["status"], "pending")
        self.assertEqual(self.stock(), 3)

    def test_cod_confirmation_failure_rolls_back_ledger_and_paid(self):
        self.add()
        order = self.checkout()[1]
        for state in ("confirmed", "packing", "shipping", "delivered"):
            self.status(order["id"], state)
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("failure")):
            self.assertEqual(self.admin_call("POST", f"/admin/orders/{order['id']}/cod/confirm", {"collection_reference": "TEST-RECEIPT"})[0], 500)
        self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "unpaid")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.Payment)), 0)

    def test_missing_config_blocks_online_checkout_without_consuming_cart(self):
        from fastapi import HTTPException
        self.add()
        body = self.shipping()
        body["payment_method"] = "vnpay"
        with patch("app.services.payment_providers.get_provider", side_effect=HTTPException(status_code=503, detail="Unavailable")):
            self.assertEqual(self.checkout(body)[0], 503)
        self.assertEqual(self.order_count(), 0)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.cart_call()[1]["total_quantity"], 1)

    def test_ownership_config_and_online_fulfilment_guard(self):
        order, _ = self.online_order()
        self.assertEqual(self.cart_call("POST", f"/orders/{order['id']}/payments/vnpay", other=True)[0], 404)
        self.status(order["id"], "confirmed")
        self.assertEqual(self.status(order["id"], "packing")[0], 409)
        from app.services.payment_providers import VNPaySandbox
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Exception) as error:
                VNPaySandbox.from_environment()
            self.assertEqual(error.exception.status_code, 503)

    def test_payment_method_validation_and_schema(self):
        body = self.shipping()
        body["payment_method"] = "momo"
        self.assertEqual(self.checkout(body)[0], 422)
        self.assertEqual(self.admin_call("POST", "/admin/orders/1/cod/confirm", {"collection_reference": "proof", "payment_status": "paid"})[0], 422)
        from app.services.payment_providers import VNPaySandbox
        for amount in (Decimal("0"), Decimal("10000000000"), Decimal("1.001")):
            with self.assertRaises(Exception):
                VNPaySandbox.amount_units(amount)

    def test_new_payment_migration_offline(self):
        from alembic import command
        from alembic.config import Config
        output = io.StringIO()
        command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output), "20261016_0003:20261016_0004", sql=True)
        sql = output.getvalue()
        self.assertIn("CREATE TABLE payment_transactions", sql)
        self.assertIn("ADD COLUMN payment_method", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("DELETE FROM", sql)

    def test_staff_cod_confirmation_audit_and_cross_role_retry(self):
        for staff, actor_id in ((True, 4), (False, 3)):
            self.add()
            order = self.checkout()[1]
            for state in ("confirmed", "packing", "shipping", "delivered"):
                self.status(order["id"], state)
            path = f"/staff/orders/{order['id']}/cod/confirm"
            receipt = f"TEST-COLLECTION-{order['id']}"
            status, result, _ = self.admin_call("POST", path, {"collection_reference": receipt}, staff=staff)
            self.assertEqual(status, 200)
            before = self.payment(result["id"])
            self.assertEqual(before["confirmed_by"], actor_id)
            self.assertIsNotNone(before["verified_at"])
            self.assertEqual(before["provider_transaction_id"], receipt)
            self.assertEqual(before["amount_vnd"], Decimal(order["total_vnd"]))
            self.assertEqual(self.cart_call(path=f"/orders/{order['id']}")[1]["payment_status"], "paid")
            # Retrying from either route must preserve the original confirmation.
            self.assertEqual(self.admin_call("POST", path, {"collection_reference": receipt}, staff=not staff)[1]["id"], result["id"])
            self.assertEqual(self.admin_call("POST", f"/admin/orders/{order['id']}/cod/confirm", {"collection_reference": receipt})[1]["id"], result["id"])
            self.assertEqual(self.payment(result["id"]), before)
            self.assertEqual(self.admin_call("POST", path, {"collection_reference": "DIFFERENT-RECEIPT"}, staff=staff)[0], 409)
        self.assertEqual(self.stock(), 3)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.Payment)), 2)

    def test_staff_cod_permissions_and_service_role_checks(self):
        self.add()
        ident = self.checkout()[1]["id"]
        path = f"/staff/orders/{ident}/cod/confirm"
        payload = {"collection_reference": "TEST-RECEIPT"}
        self.assertEqual(self.cart_call("POST", path, payload, anonymous=True)[0], 401)
        self.assertEqual(self.cart_call("POST", path, payload)[0], 403)
        self.assertEqual(self.admin_call("POST", f"/admin/orders/{ident}/cod/confirm", payload, staff=True)[0], 403)
        from app.services.payments import confirm_cod
        from fastapi import HTTPException
        for actor_id, allow_staff in ((1, True), (4, False)):
            with Session(self.engine) as db, self.assertRaises(HTTPException) as error:
                confirm_cod(db, actor_id, ident, "TEST-RECEIPT", allow_staff=allow_staff)
            self.assertEqual(error.exception.status_code, 403)

    def test_staff_cod_invalid_states_and_methods(self):
        self.add()
        ident = self.checkout()[1]["id"]
        path = f"/staff/orders/{ident}/cod/confirm"
        body = {"collection_reference": "TEST-RECEIPT"}
        for state in ("pending", "confirmed", "packing", "shipping"):
            if state != "pending":
                self.status(ident, state)
            self.assertEqual(self.admin_call("POST", path, body, staff=True)[0], 409)
        self.status(ident, "delivered")
        with Session(self.engine) as db, db.begin():
            db.get(self.Order, ident).payment_method = "vnpay"
        self.assertEqual(self.admin_call("POST", path, body, staff=True)[0], 409)
        with Session(self.engine) as db, db.begin():
            order = db.get(self.Order, ident)
            order.payment_method = "cod"
            order.payment_status = "paid"  # Simulate inconsistent legacy data, no receipt.
        self.assertEqual(self.admin_call("POST", path, body, staff=True)[0], 409)
        self.add()
        cancelled = self.checkout()[1]["id"]
        self.status(cancelled, "cancelled")
        self.assertEqual(self.admin_call("POST", f"/staff/orders/{cancelled}/cod/confirm", body, staff=True)[0], 409)

    def test_staff_cod_validation_and_missing_order(self):
        path = "/staff/orders/999/cod/confirm"
        self.assertEqual(self.admin_call("POST", path, {"collection_reference": "TEST-RECEIPT"}, staff=True)[0], 404)
        for payload in ({}, {"collection_reference": " "}, {"collection_reference": "ab"},
                        {"collection_reference": "a\x00b"}, {"collection_reference": "a" * 101},
                        {"collection_reference": "TEST", "amount_vnd": "0.01"},
                        {"collection_reference": "TEST", "payment_status": "paid"},
                        {"collection_reference": "TEST", "confirmed_by": 3}):
            with self.subTest(payload=payload):
                self.assertEqual(self.admin_call("POST", path, payload, staff=True)[0], 422)

    def test_staff_cod_database_failure_rolls_back(self):
        self.add()
        ident = self.checkout()[1]["id"]
        for state in ("confirmed", "packing", "shipping", "delivered"):
            self.status(ident, state)
        path = f"/staff/orders/{ident}/cod/confirm"
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private-driver-error")):
            status, body, _ = self.admin_call("POST", path, {"collection_reference": "TEST-RECEIPT"}, staff=True)
        self.assertEqual(status, 500)
        self.assertNotIn("private-driver-error", json.dumps(body))
        self.assertEqual(self.cart_call(path=f"/orders/{ident}")[1]["payment_status"], "unpaid")
        self.assertEqual(self.stock(), 4)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(sa.select(sa.func.count()).select_from(self.Payment)), 0)


if __name__ == "__main__":
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only):
        unittest.main()
