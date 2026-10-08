import pandas as pd
import random


customers=pd.read_csv(
"output/customers.csv"
)


products=pd.read_csv(
"output/products.csv"
)



data=[]


for i in range(10000):


    c=random.choice(
        customers.CustomerID.tolist()
    )


    p=random.choice(
        products.ProductID.tolist()
    )


    data.append({

    "CustomerID":c,

    "ProductID":p,

    "Action":
    random.choice([
        "View",
        "Click",
        "AddCart",
        "Purchase"
    ])

    })



pd.DataFrame(data).to_csv(
"output/customer_behavior.csv",
index=False,
encoding="utf-8-sig"
)
