import pandas as pd
import os
import random
from faker import Faker
from datetime import datetime, timedelta



fake = Faker("vi_VN")



# số lượng đơn hàng

NUM_ORDERS = 10000



# đọc dữ liệu có sẵn

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

customers = pd.read_csv(os.path.join(BASE_DIR, "output", "customers.csv"))
products = pd.read_csv(os.path.join(BASE_DIR, "output", "products.csv"))


orders = []



# trạng thái đơn hàng

status_list = [
    "Đã giao",
    "Đang giao",
    "Đã hủy"
]



# phương thức thanh toán

payment_list = [
    "COD",
    "Chuyển khoản",
    "Ví điện tử",
    "Thẻ ngân hàng"
]



# ngày bắt đầu dữ liệu

start_date = datetime(
    2024,
    1,
    1
)



for i in range(1, NUM_ORDERS+1):


    # chọn khách hàng ngẫu nhiên

    customer = customers.sample(
        1
    ).iloc[0]



    # chọn sản phẩm ngẫu nhiên

    product = products.sample(
        1
    ).iloc[0]



    # số lượng mua

    quantity = random.randint(
        1,
        3
    )



    # lấy giá sản phẩm

    price = product["SalePrice"]



    # tính tiền

    total = quantity * price



    # ngày mua

    order_date = (
        start_date
        +
        timedelta(
            days=random.randint(
                0,
                730
            )
        )
    )



    order = {


        "OrderID":
            f"DH{i:05d}",



        "CustomerID":
            customer["CustomerID"],



        "ProductID":
            product["ProductID"],



        "OrderDate":
            order_date.strftime(
                "%Y-%m-%d"
            ),



        "Quantity":
            quantity,



        "UnitPrice":
            price,



        "TotalAmount":
            total,



        "PaymentMethod":
            random.choice(
                payment_list
            ),



        "Status":
            random.choice(
                status_list
            )

    }



    orders.append(order)





# chuyển sang dataframe

df = pd.DataFrame(
    orders
)



# lưu file

df.to_csv(
    "output/orders.csv",
    index=False,
    encoding="utf-8-sig"
)



print(
    "Đã tạo",
    NUM_ORDERS,
    "đơn hàng"
)



print(
    df.head()
)
