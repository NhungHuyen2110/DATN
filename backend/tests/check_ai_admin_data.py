
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.services.ai_admin_analytics import get_top_selling_products
from app.services.dashboard import revenue


def main():
    start_date = date(2026, 10, 1)
    end_date = date(2026, 10, 31)

    # Transaction chỉ đọc, không được phép ghi dữ liệu.
    with engine.connect() as connection:
        connection.execute(
            text("SET TRANSACTION READ ONLY")
        )

        db = Session(bind=connection)

        try:
            top_products = get_top_selling_products(
                db=db,
                start_date=start_date,
                end_date=end_date,
                limit=5,
            )

            dashboard_revenue = revenue(
                db=db,
                start_date=start_date,
                end_date=end_date,
                group_by="month",
            )

            print("\n=== TOP 5 SAN PHAM BAN CHAY ===")

            for index, item in enumerate(
                top_products["items"], start=1
            ):
                print(
                    f"{index}. {item['product_name']} | "
                    f"SL: {item['quantity_sold']} | "
                    f"Gia tri: "
                    f"{item['gross_item_value_vnd']} VND"
                )

            print("\n=== DOI CHIEU DASHBOARD ===")
            print(
                "So don thanh toan hop le:",
                dashboard_revenue.confirmed_payment_order_count
            )
            print(
                "Tong thanh toan xac nhan:",
                dashboard_revenue.confirmed_payment_amount_vnd,
                "VND"
            )

            print("\nREAD-ONLY CHECK COMPLETED")

        finally:
            db.close()
            connection.rollback()


if __name__ == "__main__":
    main()
