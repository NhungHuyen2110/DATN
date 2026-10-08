import pandas as pd
import random


orders = pd.read_csv(
    "output/orders.csv"
)


products = pd.read_csv(
    "output/products.csv"
)


details=[]


for _,order in orders.iterrows():


    number=random.randint(
        1,3
    )


    selected=products.sample(
        number
    )


    for _,p in selected.iterrows():

        details.append({

            "OrderID":
            order["OrderID"],


            "ProductID":
            p["ProductID"],


            "Quantity":
            random.randint(1,3),


            "UnitPrice":
            p["SalePrice"]

        })



df=pd.DataFrame(details)



df.to_csv(
    "output/order_details.csv",
    index=False,
    encoding="utf-8-sig"
)


print(
"Đã tạo order_details.csv"
)
