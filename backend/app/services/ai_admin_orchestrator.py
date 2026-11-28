
from decimal import Decimal, InvalidOperation
from app.services.ai_order_tools import get_order_statistics
from app.services.ai_multi_intent import normalize_question
from app.services.ai_multi_intent import analyze_multi_intent
from app.services.ai_admin_business import (
    get_revenue_statistics,
)
from app.services.ai_admin_analytics import (
    get_top_selling_products,
)
from app.services.ai_inventory_tools import (
    get_inventory_statistics,
)


def answer_purchase_behavior(db, message):
    """Admin-only entrypoint, aggregate report only; no buyer identities."""
    from .ai_multi_intent import detect_requested_tools
    if 'purchase_behavior' not in detect_requested_tools(message, 'admin'):
        return None
    from .ai_business_dialogue import parse_plan, BusinessState, Clarify
    from .purchase_behavior import analyze
    try:
        plan, _ = parse_plan(message, BusinessState(), 'admin')
        if plan.metrics != ('purchase_behavior',):
            raise Clarify('Hãy hỏi riêng chỉ số mua hàng hoặc phân tách từng nghiệp vụ.')
    except Clarify as exc:
        return {'intent': 'unsupported', 'data': None, 'answer': str(exc)}
    data = analyze(db, plan.period.start, plan.period.end)
    return {'intent': 'purchase_behavior', 'data': data,
            'answer': f"Từ {data['start_date']} đến {data['end_date']}: {data['total_orders']} đơn tạo; "
                      f"{data['unique_buyers']} người mua; {data['repeat_buyers']} người có hơn một đơn trong kỳ; "
                      f"{data['total_units']} sản phẩm trong các đơn. "
                      'Báo cáo gồm mọi trạng thái đơn theo ngày tạo, kể cả đơn hủy/chưa thanh toán; '
                      'không phải doanh thu xác nhận, lượt xem/tìm kiếm hay ý định khách hàng.'}


def format_vnd(value):
    try:
        amount = Decimal(str(value))
        return f"{amount:,.0f}".replace(",", ".") + " đ"
    except (InvalidOperation, TypeError, ValueError):
        return "Không xác định"


def resolve_period(message):
    from .ai_reporting_period import parse_reporting_period, reporting_scope_supported
    result = parse_reporting_period(message)
    if result['intent'] != 'period':
        return result
    if not reporting_scope_supported(result.pop('_remaining'), multi=True):
        return {'intent': 'unsupported', 'message': 'Chưa hỗ trợ đầy đủ bộ lọc trong yêu cầu kết hợp.'}
    return {**result, 'intent': 'revenue_statistics'}


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
    # Top-selling returns a single aggregate ranking, not a grouped series.
    import re
    if 'top_selling_products' in tools and re.search(r'\b(?:theo|moi|tung)\s+(?:ngay|thang)\b', normalize_question(message)):
        return {'intent': 'unsupported', 'tools_used': [], 'data': None,
                'answer': 'Báo cáo bán chạy chưa hỗ trợ chia nhóm theo ngày hoặc tháng.'}
    from .ai_order_scope import parse_order_scope, order_clause, statistic_value
    from .ai_reporting_period import has_period, reporting_scope_supported
    order_intent = None
    if 'order_statistics' in tools:
        order_intent = parse_order_scope(order_clause(message))
        if has_period(message) or order_intent['intent'] != 'order_statistics':
            return {'intent': 'unsupported', 'tools_used': [], 'data': None,
                    'answer': 'Chưa hỗ trợ đầy đủ bộ lọc đơn hàng trong câu hỏi kết hợp. Vui lòng hỏi riêng từng nghiệp vụ.'}
    if not any(t in tools for t in ('revenue', 'top_selling_products')) and not reporting_scope_supported(normalize_question(message), multi=True):
        return {'intent': 'unsupported', 'tools_used': [], 'data': None,
                'answer': 'Chưa hỗ trợ đầy đủ bộ lọc trong yêu cầu kết hợp.'}


    # Thống kê hiện tại, không có bộ lọc thời gian.
    needs_period = any(
        tool in tools
        for tool in ("revenue", "top_selling_products")
    )

    if needs_period:
        period_intent = resolve_period(message)

        if period_intent.get("intent") != "revenue_statistics":
            return {
                "intent": period_intent["intent"],
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


    # Công cụ thống kê đơn hàng dành cho Admin.
    if "order_statistics" in tools:
        orders = get_order_statistics(db)
        label, value = statistic_value(orders, order_intent['field'])

        sections.append(
            "THỐNG KÊ ĐƠN HÀNG (TOÀN BỘ LỊCH SỬ)\n"
            f"{label}: {value} đơn."
        )

        data["order_statistics"] = {
            "label": label,
            "value": value,
            "scope": orders["scope"],
        }

    # 3. Tồn kho hiện tại
    if "inventory" in tools:
        inventory = get_inventory_statistics(
            db=db,
            threshold=5,
            limit=20,
            mode='low_stock',
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
