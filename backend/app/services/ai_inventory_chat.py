
from app.services.ai_inventory_tools import (
    get_inventory_statistics,
)
from app.services.ai_staff_intent import normalize_text


def answer_inventory_question(db, question: str):
    """
    Trả None nếu không phải câu hỏi tồn kho.
    Chỉ đọc dữ liệu, không cập nhật sản phẩm.
    """

    text = normalize_text(question)

    inventory_words = (
        "ton kho",
        "sap het hang",
        "het hang",
        "hang ton",
        "stock",
    )

    if not any(word in text for word in inventory_words):
        return None

    # Chưa hỗ trợ kết hợp nhiều nghiệp vụ.
    combined_words = (
        "doanh thu",
        "ban chay",
        "don hang",
        "nhap them bao nhieu",
    )

    if any(word in text for word in combined_words):
        return {
            "answer": (
                "Hiện tại vui lòng hỏi thống kê tồn kho "
                "và các nghiệp vụ khác thành từng câu riêng."
            ),
            "intent": "unsupported",
            "data": None,
        }

    # Chưa hỗ trợ tra cứu tồn kho theo tên hoặc SKU.
    if any(
        phrase in text
        for phrase in (
            "con bao nhieu chiec",
            "con bao nhieu cai",
            "ma sku",
        )
    ):
        return {
            "answer": (
                "Tôi chưa hỗ trợ tra cứu tồn kho theo "
                "từng sản phẩm cụ thể."
            ),
            "intent": "unsupported",
            "data": None,
        }

    result = get_inventory_statistics(
        db=db,
        threshold=5,
        limit=20,
    )

    out_count = result["out_of_stock_products"]
    low_count = result["low_stock_products"]

    # Phân biệt hết hàng và sắp hết hàng.
    if "het hang" in text and "sap het hang" not in text:
        mode = "out_of_stock"
        products = [
            p for p in result["products"]
            if p["inventory_status"] == "out_of_stock"
        ]
        count = out_count
        label = "đã hết hàng"

    else:
        mode = "low_stock"
        products = [
            p for p in result["products"]
            if p["inventory_status"] == "low_stock"
        ]
        count = low_count
        label = "sắp hết hàng"

    lines = [
        f"Hiện có {count} sản phẩm {label} "
        "trong hệ thống LUMIÈRE."
    ]

    for index, product in enumerate(products, 1):
        lines.append(
            f"{index}. {product['product_name']} "
            f"(SKU: {product['sku']}) - "
            f"còn {product['stock']} chiếc."
        )

    if count > len(products):
        lines.append(
            f"Đang hiển thị {len(products)}/{count} sản phẩm."
        )

    return {
        "answer": "\n".join(lines),
        "intent": "inventory_statistics",
        "field": mode,
        "data": {
            "total_products": result["total_products"],
            "out_of_stock_products": out_count,
            "low_stock_products": low_count,
            "threshold": result["low_stock_threshold"],
            "products": products,
        },
    }
