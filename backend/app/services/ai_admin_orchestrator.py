
import re
from decimal import Decimal, InvalidOperation

from app.services.ai_multi_intent import analyze_multi_intent
from app.services.ai_admin_revenue_intent import (
    understand_revenue_question,
)
from app.services.ai_admin_business import (
    get_revenue_statistics,
)
from app.services.ai_admin_analytics import (
    get_top_selling_products,
)
from app.services.ai_inventory_tools import (
    get_inventory_statistics,
)


def format_vnd(value):
    try:
        amount = Decimal(str(value))
        return f"{amount:,.0f}".replace(",", ".") + " đ"
    except (InvalidOperation, TypeError, ValueError):
        return "Không xác định"


def resolve_period(message):
    """
    Tách mốc thời gian dùng chung cho các công cụ.

    Không truyền toàn bộ câu hỏi kết hợp vào
    understand_revenue_question(), vì hàm đó
    cố ý từ chối multi-intent.
    """
    text = message.lower()

    months = re.findall(
        r"tháng\s+(\d{1,2})"
        r"(?:\s*(?:/|năm)\s*(\d{4}))?",
        text,
    )

    relative = [
        phrase
        for phrase in (
            "hôm nay",
            "hôm qua",
            "tháng trước",
            "tháng này",
        )
        if phrase in text
    ]

    # Nhiều mốc thời gian: không tự đoán.
    if len(months) + len(relative) > 1:
        return {
            "intent": "invalid",
            "message": (
                "Câu hỏi có nhiều mốc thời gian. "
                "Vui lòng chọn một khoảng thời gian "
                "chung cho doanh thu và sản phẩm bán chạy."
            ),
        }

    if months:
        month, year = months[0]
        period = f"tháng {month}"
        if year:
            period += f"/{year}"

    elif relative:
        period = relative[0]

    else:
        # Không âm thầm hiểu các dạng ngày chưa hỗ trợ.
        if re.search(
            r"\b(?:ngày|tuần|quý|năm)\b", text
        ):
            return {
                "intent": "invalid",
                "message": (
                    "Tôi chưa hỗ trợ mốc thời gian này "
                    "trong câu hỏi kết hợp. "
                    "Hãy dùng tháng 10/2026, "
                    "tháng này, tháng trước, "
                    "hôm nay hoặc hôm qua."
                ),
            }

        period = "tháng này"

    # Chỉ đưa câu hỏi một nghiệp vụ
    # cho bộ phân tích doanh thu hiện có.
    return understand_revenue_question(
        f"Doanh thu {period} là bao nhiêu?"
    )


def answer_admin_multi_intent(db, message: str):
    """
    Orchestrator chỉ đọc cho Admin.

    Phải được gọi từ endpoint đã xác thực Admin.
    Không gọi trực tiếp từ endpoint công khai.
    """

    plan = analyze_multi_intent(message, "admin")

    if not plan["is_multi_intent"]:
        return None

    tools = plan["tools"]
    sections = []
    data = {}

    # Thống kê hiện tại, không có bộ lọc thời gian.
    needs_period = any(
        tool in tools
        for tool in ("revenue", "top_selling_products")
    )

    if needs_period:
        period_intent = resolve_period(message)

        if period_intent.get("intent") != "revenue_statistics":
            return {
                "intent": "invalid",
                "tools_used": [],
                "answer": period_intent.get(
                    "message",
                    "Không xác định được khoảng thời gian."
                ),
                "data": None,
            }

        start_date = period_intent["start_date"]
        end_date = period_intent["end_date"]
        group_by = period_intent["group_by"]

        period_label = (
            f"{start_date:%d/%m/%Y} "
            f"đến {end_date:%d/%m/%Y}"
        )

    else:
        start_date = None
        end_date = None
        group_by = None
        period_label = None

    # 1. Doanh thu đã xác nhận
    if "revenue" in tools:
        revenue = get_revenue_statistics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )

        amount = revenue[
            "confirmed_payment_amount_vnd"
        ]
        orders = revenue[
            "confirmed_payment_order_count"
        ]

        sections.append(
            f"DOANH THU ({period_label})\n"
            f"Tổng thanh toán xác nhận: "
            f"{format_vnd(amount)}.\n"
            f"Số đơn có thanh toán xác nhận: "
            f"{orders}."
        )

        data["revenue"] = revenue

    # 2. Sản phẩm bán chạy cùng kỳ
    if "top_selling_products" in tools:
        top_selling = get_top_selling_products(
            db=db,
            start_date=start_date,
            end_date=end_date,
            limit=5,
        )

        items = top_selling["items"]

        lines = [
            f"SẢN PHẨM BÁN CHẠY ({period_label})"
        ]

        if not items:
            lines.append(
                "Không có sản phẩm bán chạy "
                "trong khoảng thời gian này."
            )
        else:
            for index, item in enumerate(items, 1):
                lines.append(
                    f"{index}. {item['product_name']}: "
                    f"{item['quantity_sold']} sản phẩm, "
                    f"giá trị bán hàng "
                    f"{format_vnd(item['gross_item_value_vnd'])}."
                )

        sections.append("\n".join(lines))
        data["top_selling_products"] = top_selling

    # 3. Tồn kho hiện tại
    if "inventory" in tools:
        inventory = get_inventory_statistics(
            db=db,
            threshold=5,
            limit=20,
        )

        low = inventory["low_stock_products"]
        out = inventory["out_of_stock_products"]

        lines = [
            "TỒN KHO HIỆN TẠI",
            f"Sản phẩm sắp hết hàng (còn 1–5): {low}.",
            f"Sản phẩm đã hết hàng: {out}.",
        ]

        low_products = [
            p
            for p in inventory["products"]
            if p["inventory_status"] == "low_stock"
        ]

        if low_products:
            lines.append("Các sản phẩm sắp hết hàng:")

            for index, product in enumerate(
                low_products, 1
            ):
                lines.append(
                    f"{index}. "
                    f"{product['product_name']} "
                    f"(SKU: {product['sku']}) – "
                    f"còn {product['stock']} chiếc."
                )

            if low > len(low_products):
                lines.append(
                    f"Đang hiển thị "
                    f"{len(low_products)}/{low} sản phẩm."
                )

        sections.append("\n".join(lines))
        data["inventory"] = inventory

    return {
        "intent": "multi_intent",
        "tools_used": tools,
        "answer": "\n\n".join(sections),
        "data": data,
    }
