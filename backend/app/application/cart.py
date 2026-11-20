from decimal import Decimal, localcontext

from app.domain.cart import CartRecord, CartRepository, check_stock


class CartService:
    def __init__(self, repository: CartRepository):
        self.repository = repository

    def _response(self, cart: CartRecord | None) -> dict:
        if cart is None:
            return {"id": None, "items": [], "total_quantity": 0, "subtotal_vnd": Decimal("0.00")}
        items = self.repository.items(cart.id)
        result = []
        with localcontext() as context:
            context.prec = 50
            subtotal = Decimal("0.00")
            for item in items:
                product = item.product
                line_total = product.sale_price * item.quantity
                subtotal += line_total
                result.append({
                    "id": item.id,
                    "product": {"id": product.id, "sku": product.sku, "name": product.name, "stock": product.stock},
                    "quantity": item.quantity, "unit_price_vnd": product.sale_price,
                    "line_total_vnd": line_total, "in_stock": item.quantity <= product.stock,
                })
        return {"id": cart.id, "items": result, "total_quantity": sum(i.quantity for i in items), "subtotal_vnd": subtotal}

    def get(self, user_id: int) -> dict:
        return self._response(self.repository.find(user_id))

    def add(self, user_id: int, product_id: int, quantity: int) -> dict:
        with self.repository.mutation(user_id):
            cart = self.repository.find(user_id)
            item = None if cart is None else self.repository.find_product_item(cart.id, product_id)
            quantity += item.quantity if item is not None else 0
            product = self.repository.lock_product(product_id)
            check_stock(product, quantity)
            if cart is None:
                cart = self.repository.create(user_id)
            if item is None:
                self.repository.add(cart.id, product.id, quantity)
            else:
                item.quantity = quantity
            self.repository.flush()
            result = self._response(cart)
        return result

    def update(self, user_id: int, item_id: int, quantity: int) -> dict:
        with self.repository.mutation(user_id):
            cart = self.repository.find(user_id)
            item = self.repository.owned_item(cart, item_id)
            check_stock(self.repository.lock_product(item.product_id), quantity)
            item.quantity = quantity
            self.repository.flush()
            result = self._response(cart)
        return result

    def delete(self, user_id: int, item_id: int) -> dict:
        with self.repository.mutation(user_id):
            cart = self.repository.find(user_id)
            self.repository.delete(self.repository.owned_item(cart, item_id))
            self.repository.flush()
            result = self._response(cart)
        return result
