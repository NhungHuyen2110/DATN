import pandas as pd
import random


customers=pd.read_csv(
"output/customers.csv"
)


keywords=[
"nhẫn vàng",
"dây chuyền kim cương",
"bông tai bạc",
"vòng tay nữ",
"trang sức cưới"
]


data=[]


for i in range(5000):


    data.append({

    "CustomerID":
    random.choice(
    customers.CustomerID.tolist()
    ),


    "Keyword":
    random.choice(keywords)

    })



pd.DataFrame(data).to_csv(
"output/search_history.csv",
index=False,
encoding="utf-8-sig"
)
