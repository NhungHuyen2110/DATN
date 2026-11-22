
from .role import Role
from .product_attribute_review import ProductAttributeReview
from .user import User
from .user_session import UserSession
from .category import Category
from .brand import Brand
from .material import Material
from .gemstone import Gemstone
from .collection import Collection
from .product import Product
from .cart import Cart
from .cart_item import CartItem
from .order import Order
from .order_item import OrderItem
from .payment_transaction import PaymentTransaction
from .customer_content import WishlistItem, ProductReview
from .coupon import Coupon, CouponUsage

from .contact_message import ContactMessage
from .product_index_job import ProductIndexJob
# Register the feature-gated transactional hook after all business models load.
from app.services import product_index_jobs as _product_index_jobs
