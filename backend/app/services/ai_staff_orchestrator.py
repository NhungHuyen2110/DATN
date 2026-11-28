
from app.services.ai_multi_intent import (
    analyze_multi_intent,
    normalize_question,
)
from app.services.ai_order_tools import get_order_statistics
from app.services.ai_inventory_tools import get_inventory_statistics


def answer_staff_multi_intent(db, message: str):
    """
    Điều phối câu hỏi nhiều nghiệp vụ cho Staff.
    Chỉ dùng trong endpoint đã kiểm tra quyền Staff/Admin.
    Không cập nhật dữ liệu.
    """

    plan = analyze_multi_intent(message, "staff")

    # Câu hỏi đơn nghiệp vụ vẫn chạy theo luồng cũ.
    if not plan["is_multi_intent"]:
        return None

    tools = plan["tools"]
    text = normalize_question(message)

    from .ai_order_scope import parse_order_scope, order_clause, statistic_value
    from .ai_reporting_period import has_period, reporting_scope_supported
    order_intent = parse_order_scope(order_clause(message))
    if has_period(message) or order_intent['intent'] != 'order_statistics' or not reporting_scope_supported(text, multi=True):
        return {'intent': 'unsupported', 'data': None,
                'answer': 'Chưa hỗ trợ đầy đủ bộ lọc trong câu hỏi kết hợp. Vui lòng hỏi riêng thống kê đơn và tồn kho.'}

    answers = []
    data = {}

    # Công cụ 1: Thống kê đơn hàng
    if "order_statistics" in tools:
        orders = get_order_statistics(db)

        label, value = statistic_value(orders, order_intent['field'])

        answers.append(f"{label}: {value} đơn.")

        data["order_statistics"] = {
            "label": label,
            "value": value,
            "scope": orders["scope"],
        }

    # Công cụ 2: Tồn kho
    if "inventory" in tools:
        inventory = get_inventory_statistics(
            db=db,
            threshold=5,
            limit=20,
            mode='out_of_stock' if 'het hang' in text and 'sap het hang' not in text else 'low_stock',
        )

        only_out_of_stock = (
            "het hang" in text
            and "sap het hang" not in text
        )

        if only_out_of_stock:
            count = inventory["out_of_stock_products"]
            status = "out_of_stock"
            label = "đã hết hàng"
        else:
            count = inventory["low_stock_products"]
            status = "low_stock"
            label = "sắp hết hàng"

        products = [
            p for p in inventory["products"]
            if p["inventory_status"] == status
        ]

        lines = [f"Có {count} sản phẩm {label}."]

        for index, p in enumerate(products, 1):
            lines.append(
                f"{index}. {p['product_name']} "
                f"(SKU: {p['sku']}) - "
                f"còn {p['stock']} chiếc."
            )

        if count > len(products):
            lines.append(
                f"Đang hiển thị {len(products)}/{count} sản phẩm."
            )

        answers.append("\n".join(lines))

        data["inventory"] = {
            "count": count,
            "threshold": 5,
            "products": products,
        }

    return {
        "intent": "multi_intent",
        "tools_used": tools,
        "answer": "\n\n".join(answers),
        "data": data,
    }
