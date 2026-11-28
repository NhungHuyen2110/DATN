
import re

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Product
from .ai_staff_intent import normalize_text


def extract_product_query(message: str):
    """
    Chỉ nhận diện yêu cầu tra cứu sản phẩm cụ thể.
    Không xử lý câu hỏi thống kê tồn kho tổng quát.
    """
    if not isinstance(message, str):
        return None

    message = message.strip()
    text = normalize_text(message)

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
        remaining = re.sub(re.escape(skus[0]), ' ', text, flags=re.I)
        if set(re.findall(r'\w+', remaining)) - set('tim kiem san pham sku ma tra cuu ton kho con hang khong bao nhieu chiec cai thong tin cho toi biet'.split()):
            return {'type': 'unsupported', 'value': message}
        return {
            "type": "sku",
            "value": skus[0],
        }

    explicit_sku = re.fullmatch(r'(?:.*?\b)?sku\s*[:=]?\s*([a-z0-9_-]{1,50})\s*\??', text)
    if explicit_sku:
        prefix = text[:explicit_sku.start(1)]
        if set(re.findall(r'\w+', prefix)) <= set('tim kiem san pham sku ma tra cuu ton kho thong tin'.split()):
            return {'type': 'sku', 'value': explicit_sku[1].upper()}
        return {'type': 'unsupported', 'value': message}
    attribute_labels = {'loai': 'category', 'chat lieu': 'material', 'da': 'gemstone',
                        'thuong hieu': 'brand', 'bo suu tap': 'collection'}
    if re.match(r'^(?:tim|tra cuu|liet ke)\s+(?:san pham)\s+', text):
        body = re.sub(r'^(?:tim|tra cuu|liet ke)\s+san pham\s+', '', text).strip(' ?')
        if any(body.startswith(label + ' ') for label in attribute_labels):
            attributes = {}
            for part in re.split(r'\s+va\s+|[,;]', body):
                for label, key in attribute_labels.items():
                    if part.startswith(label + ' ') and key not in attributes:
                        attributes[key] = part[len(label):].strip(' :=?')
                        break
                else:
                    return {'type': 'unsupported', 'value': message}
            return {'type': 'attributes', 'value': body, 'attributes': attributes}
    # Name grammar; normalize only for matching, never broaden unknown filters.
    match = re.fullmatch(
        r"(?:tim|tra cuu)\s+(?:kiem\s+)?san\s+pham\s+(.+?)\s*\??",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return {
            "type": "name",
            "value": match.group(1).strip(),
        }

    # "Nhẫn Golden Dream còn hàng không?"
    match = re.fullmatch(
        r"(.+?)\s+con\s+hang\s+khong\s*\??",
        text,
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

    if query['type'] == 'unsupported':
        return {'intent': 'unsupported', 'data': None, 'answer': 'Chưa hiểu đầy đủ bộ lọc sản phẩm; vui lòng nêu tên, SKU hoặc thuộc tính được hỗ trợ.'}

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
        stmt = stmt.where(func.lower(Product.sku) == value.lower())

    if query['type'] == 'sku':
        products = db.scalars(stmt.order_by(Product.id.asc()).limit(6)).all()
    else:
        # Stream the authoritative catalog, bounded memory; stop after six matches.
        # No unaccent extension/schema changes required on PostgreSQL or offline SQLite.
        from sqlalchemy.orm import selectinload
        if query['type'] == 'attributes':
            for key in query['attributes']:
                stmt = stmt.options(selectinload(getattr(Product, key)))
        products = []
        with db.scalars(stmt.order_by(Product.id.asc()).execution_options(yield_per=128)) as rows:
            for product in rows:
                matches = (normalize_text(value) in normalize_text(product.name) if query['type'] == 'name'
                           else all(normalize_text(v) == normalize_text(getattr(product, k).name)
                                    for k, v in query['attributes'].items()))
                if matches:
                    products.append(product)
                    if len(products) == 6:
                        break

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
