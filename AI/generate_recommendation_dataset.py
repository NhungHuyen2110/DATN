import pandas as pd
import json


# Đọc dữ liệu

customers = pd.read_csv(
    "output/customers.csv"
)


orders = pd.read_csv(
    "output/orders.csv"
)


wishlist = pd.read_csv(
    "output/wishlist.csv"
)


reviews = pd.read_csv(
    "output/reviews.csv"
)


products = pd.read_csv(
    "output/products.csv"
)



dataset = []



# tạo hồ sơ từng khách hàng

for customer_id in customers["CustomerID"]:


    # sản phẩm đã mua

    purchased = orders[
        orders["CustomerID"] == customer_id
    ]["ProductID"].tolist()



    # sản phẩm yêu thích

    favorite = wishlist[
        wishlist["CustomerID"] == customer_id
    ]["ProductID"].tolist()



    # đánh giá

    rating = reviews[
        reviews["CustomerID"] == customer_id
    ][
        "Rating"
    ].mean()



    data = {


        "CustomerID":
        customer_id,


        "PurchasedProducts":
        purchased,


        "WishlistProducts":
        favorite,


        "AverageRating":
        round(
            rating if pd.notna(rating) else 0,
            2
        )

    }


    dataset.append(data)




# ghi ra JSON

with open(
    "AI/recommendation_dataset.json",
    "w",
    encoding="utf-8"
) as f:


    json.dump(
        dataset,
        f,
        ensure_ascii=False,
        indent=4
    )



print(
    "Đã tạo recommendation_dataset.json"
)
