"""Customer-only responses grounded in verified shopping context."""

from jewelry_agents.dialogue_state import ShoppingState


def money(value):
    return f"{value:,}".replace(",", ".") + " đồng"


def describe_budget(state):
    if not isinstance(state, ShoppingState):
        return ""

    parts = []

    if state.min_price is not None:
        prefix = "trên " if state.min_exclusive else "từ "
        parts.append(prefix + money(state.min_price))

    if state.max_price is not None:
        prefix = "dưới " if state.max_exclusive else "không quá "
        parts.append(prefix + money(state.max_price))

    return " và ".join(parts)


def shopping_summary(state, products):
    if not isinstance(state, ShoppingState) or not products:
        return ""

    categories = {
        str(p["Category"])
        for p in products
        if p.get("Category")
    }

    materials = {
        str(p["Material"])
        for p in products
        if p.get("Material")
    }

    category = (
        next(iter(categories))
        if len(categories) == 1
        else "trang sức"
    )

    subject = category.lower()

    if state.material and len(materials) == 1:
        subject += " " + next(iter(materials))

    budget = describe_budget(state)

    if budget:
        subject += ", với ngân sách " + budget

    return subject


def compact_shopping_answer(state, response, previous_state=None):

    products = response.get("products") or []

    if not products or not isinstance(state, ShoppingState):
        return None

    if response.get("status") not in {"ok", "degraded"}:
        return None

    subject = shopping_summary(state, products)

    if not subject:
        return None

    lines = []

    if isinstance(previous_state, ShoppingState):

        if previous_state.category != state.category:
            lines.append("Mình đã chuyển sang loại trang sức bạn vừa chọn.")

        if previous_state.material and not state.material:
            lines.append("Mình đã bỏ giới hạn về chất liệu.")

        if (
            previous_state.min_price != state.min_price
            or previous_state.max_price != state.max_price
        ):
            budget = describe_budget(state)
            if budget:
                lines.append("Mình đã cập nhật ngân sách " + budget + ".")

        if previous_state.price_preference != state.price_preference:
            if state.price_preference == "affordable":
                lines.append("Mình sẽ ưu tiên những mẫu có giá dễ chịu hơn.")
            elif state.price_preference == "neutral":
                lines.append("Mình không ưu tiên giá thấp nữa.")

    if state.price_preference == "affordable" and not lines:
        lines.append("Mình ưu tiên các lựa chọn giúp bạn tiết kiệm hơn.")

    lines.append(
        f"Mình tìm được {len(products)} mẫu {subject} "
        "để bạn cân nhắc."
    )

    if len(products) < state.top_k:
        lines.append(
            "Hiện chỉ có từng ấy mẫu trong kết quả phù hợp."
        )

    if response.get("status") == "degraded":
        lines.append(
            "Một nguồn tìm kiếm đang gián đoạn, "
            "nên kết quả có thể chưa đầy đủ."
        )

    return " ".join(lines)



def product_label(product):
    name = str(product.get("ProductName") or "Sản phẩm")
    product_id = product.get("ProductID", product.get("id"))

    if product_id is not None:
        return f"{name} (mã {product_id})"

    return name


def explain_previous_products(row):

    previous = row.get("last_result") or {}
    products = previous.get("products") or []

    if not products:
        return None

    state = row.get("shopping_state")

    names = [
        product_label(p)
        for p in products
    ]

    lines = [
        "Mình gợi ý các mẫu " + "; ".join(names)
        + " dựa trên yêu cầu tìm kiếm trước đó của bạn."
    ]

    summary = shopping_summary(state, products)

    if summary:
        lines.append("Yêu cầu đang áp dụng là " + summary + ".")

    if isinstance(state, ShoppingState):
        if state.price_preference == "affordable":
            lines.append(
                "Thứ hạng có tính đến sở thích tiết kiệm "
                "của bạn bên cạnh độ liên quan."
            )

    for p in products:
        reason = p.get("reason")

        if isinstance(reason, str) and reason.strip():
            lines.append(
                product_label(p)
                + ": " + reason.rstrip(".") + "."
            )

    lines.append(
        "Đây là giải thích cho danh sách vừa đề xuất, "
        "không phải một lần tìm kiếm mới."
    )

    return {
        "success": True,
        "status": "conversation_explanation",
        "intent": "conversation_explanation",
        "answer": "\n".join(lines),
        "products": [],
        "referenced_product_ids": [
            p.get("ProductID", p.get("id"))
            for p in products
        ],
        "response_mode": "contextual_grounded_explanation"
    }
