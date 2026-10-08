import pandas as pd
import random


# đọc dữ liệu có sẵn
customers = pd.read_csv(
    "output/customers.csv"
)

products = pd.read_csv(
    "output/products.csv"
)


wishlist = []


# tạo 3000 lượt yêu thích

for i in range(3000):

    customer = random.choice(
        customers["CustomerID"].tolist()
    )


    product = random.choice(
        products["ProductID"].tolist()
    )


    wishlist.append({

        "WishlistID":
        f"WL{i+1:05d}",


        "CustomerID":
        customer,


        "ProductID":
        product

    })



# tạo dataframe

df = pd.DataFrame(
    wishlist
)



# xuất file

df.to_csv(
    "output/wishlist.csv",
    index=False,
    encoding="utf-8-sig"
)



print(
    "Đã tạo wishlist.csv"
)


print(
    df.head()
)
