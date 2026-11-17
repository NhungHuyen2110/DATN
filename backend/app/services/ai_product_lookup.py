
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


def extract_product_query(message: str):
    """
    Chỉ nhận diện yêu cầu tra cứu sản phẩm cụ thể.
    Không xử lý câu hỏi thống kê tồn kho tổng quát.
    """
    if not isinstance(message, str):
        return None

    message = message.strip()

    if not message or len(message) > 1000:
        return None

    # Ưu tiên tìm SKU rõ ràng.
    skus = list(dict.fromkeys(
        s.upper()
        for s in re.findall(
            r"(?<![A-Za-z0-9])SP\d{6}(?![A-Za-z0-9])",
            message,
            flags=re.IGNORECASE,
        )
    ))

    if len(skus) > 1:
        return {
            "type": "multiple_skus",
            "values": skus,
        }

    if len(skus) == 1:
        return {
            "type": "sku",
            "value": skus[0],
        }

    # Tìm theo tên: "Tìm sản phẩm Bông tai Angel"
    match = re.fullmatch(
        r"(?:tìm|tim)\s+"
        r"(?:kiếm\s+)?"
        r"sản\s+phẩm\s+(.+?)\s*\??",
        message,
        flags=re.IGNORECASE,
    )

    if match:
        return {
            "type": "name",
            "value": match.group(1).strip(),
        }

    # "Nhẫn Golden Dream còn hàng không?"
    match = re.fullmatch(
        r"(.+?)\s+còn\s+hàng\s+không\s*\??",
        message,
        flags=re.IGNORECASE,
    )

    if match:
        return {
            "type": "name",
            "value": match.group(1).strip(),
        }

    return None


def answer_product_lookup(db: Session, message: str):
    """
    Công cụ tra cứu sản phẩm chỉ đọc.

    Chỉ được gọi từ chatbot đã xác thực quyền.
    Không cập nhật Product.stock hoặc giá bán.
    """
    query = extract_product_query(message)

    if query is None:
        return None

    if query["type"] == "multiple_skus":
        return {
            "intent": "product_lookup",
            "answer": (
                "Vui lòng tra cứu từng mã SKU riêng "
                "để tránh nhầm lẫn sản phẩm."
            ),
            "data": None,
        }

    value = query["value"]

    if not value or len(value) > 120:
        return {
            "intent": "invalid",
            "answer": "Tên hoặc mã sản phẩm không hợp lệ.",
            "data": None,
        }

    stmt = select(Product)

    if query["type"] == "sku":
        stmt = stmt.where(Product.sku == value)
    else:
        # Escape ký tự LIKE để không mở rộng truy vấn
        # khi tên có %, _ hoặc dấu gạch chéo ngược.
        safe_name = (
            value.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        stmt = stmt.where(
            Product.name.ilike(
                f"%{safe_name}%",
                escape="\\",
            )
        )

    products = db.scalars(
        stmt.order_by(Product.id.asc()).limit(6)
    ).all()

    if not products:
        return {
            "intent": "product_lookup",
            "answer": (
                f"Không tìm thấy sản phẩm phù hợp "
                f"với '{value}'."
            ),
            "data": {
                "query": value,
                "products": [],
            },
        }

    has_more = len(products) > 5
    products = products[:5]

    items = []
    lines = []

    for index, product in enumerate(products, 1):
        stock = int(product.stock)

        if stock == 0:
            status = "Hết hàng"
        elif stock <= 5:
            status = "Sắp hết hàng"
        else:
            status = "Còn hàng"

        item = {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "stock": stock,
            "status": status,
            "sale_price_vnd": str(product.sale_price),
        }

        items.append(item)

        lines.append(
            f"{index}. {product.name}\n"
            f"SKU: {product.sku}\n"
            f"Tồn kho: {stock} chiếc\n"
            f"Trạng thái: {status}\n"
            f"Giá bán: "
            f"{product.sale_price:,.0f} đ".replace(
                ",", "."
            )
        )

    answer = "\n\n".join(lines)

    if len(items) > 1:
        answer = (
            "Tìm thấy nhiều sản phẩm phù hợp:\n\n"
            + answer
        )

    if has_more:
        answer += (
            "\n\nCòn kết quả khác. "
            "Vui lòng nhập tên cụ thể hơn hoặc SKU."
        )

    return {
        "intent": "product_lookup",
        "answer": answer,
        "data": {
            "query": value,
            "lookup_type": query["type"],
            "products": items,
            "has_more": has_more,
        },
    }
