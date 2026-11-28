
from datetime import date

from app.services import ai_admin_orchestrator as admin_ai
from app.services import ai_staff_orchestrator as staff_ai


ADMIN_QUESTION = (
    "Doanh thu tháng 10/2026 bao nhiêu, "
    "sản phẩm nào bán chạy nhất và "
    "có bao nhiêu sản phẩm sắp hết hàng?"
)

STAFF_QUESTION = (
    "Có bao nhiêu đơn hàng chờ xử lý "
    "và sản phẩm nào sắp hết hàng?"
)


def fake_inventory(db, threshold=5, limit=20, mode=None):
    return {
        "total_products": 500,
        "out_of_stock_products": 0,
        "low_stock_products": 4,
        "low_stock_threshold": 5,
        "products": [
            {
                "product_id": 214,
                "sku": "SP000214",
                "product_name": "Lắc tay Eternal Love",
                "stock": 5,
                "inventory_status": "low_stock",
            }
        ],
    }


def test_admin_combines_three_tools(monkeypatch):
    calls = {}

    def fake_revenue(db, start_date, end_date, group_by):
        calls["revenue_period"] = (start_date, end_date)

        return {
            "confirmed_payment_amount_vnd": "13814291.00",
            "confirmed_payment_order_count": 3,
        }

    def fake_top(db, start_date, end_date, limit):
        calls["top_period"] = (start_date, end_date)

        return {
            "items": [
                {
                    "product_name": "Bông tai Angel",
                    "quantity_sold": 2,
                    "gross_item_value_vnd": "11194652.00",
                }
            ]
        }

    monkeypatch.setattr(
        admin_ai, "get_revenue_statistics", fake_revenue
    )
    monkeypatch.setattr(
        admin_ai, "get_top_selling_products", fake_top
    )
    monkeypatch.setattr(
        admin_ai, "get_inventory_statistics", fake_inventory
    )

    result = admin_ai.answer_admin_multi_intent(
        db=object(),
        message=ADMIN_QUESTION,
    )

    assert result["intent"] == "multi_intent"
    assert set(result["tools_used"]) == {
        "revenue",
        "top_selling_products",
        "inventory",
    }

    expected_period = (
        date(2026, 10, 1),
        date(2026, 10, 31),
    )

    # Doanh thu và bán chạy phải dùng cùng kỳ.
    assert calls["revenue_period"] == expected_period
    assert calls["top_period"] == expected_period

    assert "13.814.291" in result["answer"]
    assert "Bông tai Angel" in result["answer"]
    assert "SP000214" in result["answer"]


def test_staff_combines_orders_and_inventory(monkeypatch):
    def fake_orders(db):
        return {
            "total_orders": 9,
            "pending_orders": 3,
            "confirmed_orders": 2,
            "delivered_orders": 4,
            "scope": "all_time",
        }

    monkeypatch.setattr(
        staff_ai, "get_order_statistics", fake_orders
    )
    monkeypatch.setattr(
        staff_ai, "get_inventory_statistics", fake_inventory
    )

    result = staff_ai.answer_staff_multi_intent(
        db=object(),
        message=STAFF_QUESTION,
    )

    assert result["intent"] == "multi_intent"
    assert set(result["tools_used"]) == {
        "order_statistics",
        "inventory",
    }

    assert "3 đơn" in result["answer"]
    assert "4 sản phẩm" in result["answer"]
    assert "SP000214" in result["answer"]


def test_admin_single_question_keeps_old_flow():
    result = admin_ai.answer_admin_multi_intent(
        db=object(),
        message="Doanh thu tháng 10/2026 là bao nhiêu?",
    )

    # None nghĩa là router xử lý bằng nhánh cũ.
    assert result is None


def test_staff_single_question_keeps_old_flow():
    result = staff_ai.answer_staff_multi_intent(
        db=object(),
        message="Có bao nhiêu đơn hàng chờ xử lý?",
    )

    assert result is None


def test_admin_rejects_invalid_month():
    result = admin_ai.answer_admin_multi_intent(
        db=object(),
        message=(
            "Doanh thu tháng 13/2026, "
            "sản phẩm bán chạy và tồn kho?"
        ),
    )

    assert result["intent"] == "invalid"
    assert result["data"] is None
