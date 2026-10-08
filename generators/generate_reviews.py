import pandas as pd
import random


customers=pd.read_csv(
"output/customers.csv"
)

products=pd.read_csv(
"output/products.csv"
)


data=[]


for i in range(5000):


    data.append({

    "CustomerID":
    random.choice(
    customers.CustomerID
    ),


    "ProductID":
    random.choice(
    products.ProductID
    ),


    "Rating":
    random.randint(1,5),


    "Comment":
    random.choice([
    "Rất đẹp",
    "Chất lượng tốt",
    "Đóng gói đẹp",
    "Hài lòng"
    ])

    })



pd.DataFrame(data).to_csv(
"output/reviews.csv",
index=False,
encoding="utf-8-sig"
)
