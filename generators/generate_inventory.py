import pandas as pd
import random


products=pd.read_csv(
"output/products.csv"
)


inventory=[]


for id in products.ProductID:


    inventory.append({

    "ProductID":id,

    "Stock":
    random.randint(5,200),

    "Warehouse":
    random.choice([
        "Kho HCM",
        "Kho Hà Nội",
        "Kho Đà Nẵng"
    ])

    })



df=pd.DataFrame(
inventory
)


df.to_csv(
"output/inventory.csv",
index=False,
encoding="utf-8-sig"
)
