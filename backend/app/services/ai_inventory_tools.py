
from fastapi import HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.models import Product


def get_inventory_statistics(
    db: Session,
    threshold: int = 5,
    limit: int = 20,
):
    """
    Thống kê tồn kho LUMIÈRE.

    - Chỉ truy vấn SELECT.
    - Không cập nhật Product.stock.
    - Không thay đổi logic đặt/hủy đơn.
    - Không trả về giá vốn hoặc giá nhập.
    """

    if type(threshold) is not int or not 0 <= threshold <= 1000:
        raise HTTPException(
            status_code=422,
            detail="threshold phải từ 0 đến 1000",
        )

    if type(limit) is not int or not 1 <= limit <= 50:
        raise HTTPException(
            status_code=422,
            detail="limit phải từ 1 đến 50",
        )

    # 1. Thống kê tổng quan
    summary_query = select(
        func.count(Product.id),
        func.coalesce(
            func.sum(
                case(
                    (Product.stock == 0, 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    (
                        (Product.stock > 0)
                        & (Product.stock <= threshold),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ),
    )

    total, out_of_stock, low_stock = db.execute(
        summary_query
    ).one()

    # 2. Danh sách sản phẩm cần chú ý
    query = (
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.stock,
        )
        .where(Product.stock <= threshold)
        .order_by(Product.stock.asc(), Product.id.asc())
        .limit(limit)
    )

    rows = db.execute(query).all()

    products = []

    for product_id, sku, name, stock in rows:
        products.append({
            "product_id": product_id,
            "sku": sku,
            "product_name": name,
            "stock": stock,
            "inventory_status": (
                "out_of_stock" if stock == 0
                else "low_stock"
            ),
        })

    return {
        "total_products": int(total),
        "out_of_stock_products": int(out_of_stock),
        "low_stock_products": int(low_stock),
        "low_stock_threshold": threshold,
        "returned_count": len(products),
        "limit": limit,
        "products": products,
    }
