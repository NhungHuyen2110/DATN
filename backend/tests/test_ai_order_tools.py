
from unittest.mock import MagicMock

from app.services.ai_order_tools import (
    get_order_statistics,
)


def test_order_statistics():
    db = MagicMock()

    db.scalar.return_value = 9

    db.execute.side_effect = [
        MagicMock(
            all=MagicMock(
                return_value=[
                    ("delivered", 4),
                    ("pending", 3),
                    ("confirmed", 2),
                ]
            )
        ),
        MagicMock(
            all=MagicMock(
                return_value=[
                    ("unpaid", 5),
                    ("paid", 4),
                ]
            )
        ),
    ]

    result = get_order_statistics(db)

    assert result["total_orders"] == 9
    assert result["pending_orders"] == 3
    assert result["confirmed_orders"] == 2
    assert result["delivered_orders"] == 4
    assert result["payment_status"]["unpaid"] == 5
    assert result["payment_status"]["paid"] == 4
    assert result["scope"] == "all_time"

    # Chỉ có các thao tác đọc dữ liệu.
    db.execute.assert_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_empty_orders():
    db = MagicMock()

    db.scalar.return_value = 0
    db.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[])),
        MagicMock(all=MagicMock(return_value=[])),
    ]

    result = get_order_statistics(db)

    assert result["total_orders"] == 0
    assert result["pending_orders"] == 0
    assert result["confirmed_orders"] == 0
    assert result["delivered_orders"] == 0
    assert result["order_status"] == {}
    assert result["payment_status"] == {}


def test_unknown_status_is_preserved():
    db = MagicMock()

    db.scalar.return_value = 1
    db.execute.side_effect = [
        MagicMock(
            all=MagicMock(
                return_value=[("returned", 1)]
            )
        ),
        MagicMock(
            all=MagicMock(
                return_value=[("refunded", 1)]
            )
        ),
    ]

    result = get_order_statistics(db)

    assert result["order_status"]["returned"] == 1
    assert result["payment_status"]["refunded"] == 1
    assert result["pending_orders"] == 0
