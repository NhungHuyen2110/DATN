"""Application tests exercise monetary rules without a database or FastAPI."""

from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from app.application.cart import CartService
from app.domain.cart import CartError


class CartServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.service = CartService(self.repo)
        self.repo.mutation.side_effect = lambda user_id: nullcontext()

    def test_empty_read_has_no_write(self):
        self.repo.find.return_value = None
        self.assertEqual(self.service.get(7)["subtotal_vnd"], Decimal("0.00"))
        self.repo.mutation.assert_not_called()
        self.repo.create.assert_not_called()

    def test_extreme_monetary_totals_preserve_precision(self):
        self.repo.find.return_value = SimpleNamespace(id=4)
        product = SimpleNamespace(id=1, sku="A", name="Ring", sale_price=Decimal("9999999999999999.99"), stock=2147483647)
        item = SimpleNamespace(id=2, product=product, quantity=2147483647)
        self.repo.items.return_value = [item, item]
        self.assertEqual(self.service.get(7)["subtotal_vnd"], Decimal("42949672939999999957050327.06"))

    def test_stock_failure_never_creates_first_cart(self):
        self.repo.find.return_value = None
        self.repo.lock_product.return_value = SimpleNamespace(stock=2)
        with self.assertRaises(CartError):
            self.service.add(7, 1, 3)
        self.repo.create.assert_not_called()
        self.repo.add.assert_not_called()

    def test_duplicate_add_checks_accumulated_quantity(self):
        self.repo.find.return_value = SimpleNamespace(id=4)
        self.repo.find_product_item.return_value = SimpleNamespace(quantity=2)
        self.repo.lock_product.return_value = SimpleNamespace(stock=3)
        with self.assertRaises(CartError):
            self.service.add(7, 1, 2)
        self.repo.flush.assert_not_called()
