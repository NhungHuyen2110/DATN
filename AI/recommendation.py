import pandas as pd
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# 1. ĐỌC DỮ LIỆU
# ============================================================

print("==============================")
print("1. ĐỌC DỮ LIỆU")
print("==============================")


products = pd.read_csv(
    "../output/products_ai.csv"
)

orders = pd.read_csv(
    "../output/orders.csv"
)

order_details = pd.read_csv(
    "../output/order_details.csv"
)


print("Số sản phẩm:", len(products))
print("Số đơn hàng:", len(orders))
print("Số dòng order detail:", len(order_details))


# ============================================================
# 2. KIỂM TRA DỮ LIỆU
# ============================================================

print("\n==============================")
print("2. KIỂM TRA DỮ LIỆU")
print("==============================")


print("\nCác cột products:")
print(products.columns.tolist())


print("\n5 sản phẩm đầu tiên:")
print(
    products[
        [
            "ProductID",
            "ProductName",
            "CategoryName",
            "BrandName",
            "MaterialName",
            "GemstoneName",
            "CollectionName"
        ]
    ].head()
)


# ============================================================
# 3. TẠO CONTENT CHO SẢN PHẨM
# ============================================================

print("\n==============================")
print("3. TẠO PRODUCT CONTENT")
print("==============================")


features = [
    "ProductName",
    "CategoryName",
    "BrandName",
    "MaterialName",
    "GemstoneName",
    "CollectionName"
]


# Kiểm tra các cột có tồn tại
available_features = [
    col for col in features
    if col in products.columns
]


print("Các thuộc tính dùng cho AI:")
print(available_features)


# Thay giá trị thiếu bằng chuỗi rỗng
products[available_features] = (
    products[available_features]
    .fillna("")
)


# Ghép các thuộc tính thành một chuỗi
products["content"] = (
    products[available_features]
    .astype(str)
    .agg(" ".join, axis=1)
)


print("\nVí dụ Product Content:")

print(
    products[
        [
            "ProductName",
            "content"
        ]
    ].head()
)


# ============================================================
# 4. TF-IDF
# ============================================================

print("\n==============================")
print("4. TF-IDF")
print("==============================")


vectorizer = TfidfVectorizer(
    token_pattern=r"(?u)\b\w+\b"
)


product_matrix = vectorizer.fit_transform(
    products["content"]
)


print(
    "Kích thước ma trận TF-IDF:",
    product_matrix.shape
)


# ============================================================
# 5. COSINE SIMILARITY
# ============================================================

print("\n==============================")
print("5. COSINE SIMILARITY")
print("==============================")


similarity = cosine_similarity(
    product_matrix
)


print(
    "Kích thước ma trận similarity:",
    similarity.shape
)


# ============================================================
# 6. CONTENT-BASED RECOMMENDATION
# ============================================================

def recommend_content(
    product_id,
    number=5
):

    # Tìm vị trí sản phẩm
    matched = products[
        products["ProductID"] == product_id
    ]


    if matched.empty:

        print(
            "Không tìm thấy ProductID:",
            product_id
        )

        return pd.DataFrame()


    index = matched.index[0]


    # Lấy similarity của sản phẩm
    scores = list(
        enumerate(
            similarity[index]
        )
    )


    # Sắp xếp giảm dần
    scores = sorted(
        scores,
        key=lambda x: x[1],
        reverse=True
    )


    result = []


    current_name = products.iloc[index][
        "ProductName"
    ]


    for i, score in scores:

        # Bỏ chính sản phẩm đang xem
        if i == index:
            continue


        # Bỏ sản phẩm trùng tên
        if products.iloc[i]["ProductName"] == current_name:
            continue


        result.append(
            {
                "ProductID":
                    products.iloc[i]["ProductID"],

                "ProductName":
                    products.iloc[i]["ProductName"],

                "Category":
                    products.iloc[i]["CategoryName"],

                "Brand":
                    products.iloc[i]["BrandName"],

                "Material":
                    products.iloc[i]["MaterialName"],

                "Gemstone":
                    products.iloc[i]["GemstoneName"],

                "Collection":
                    products.iloc[i]["CollectionName"],

                "Similarity":
                    round(float(score), 3)
            }
        )


        if len(result) >= number:
            break


    return pd.DataFrame(result)


# ============================================================
# 7. TEST CONTENT-BASED
# ============================================================

print("\n==============================")
print("6. TEST CONTENT-BASED")
print("==============================")


test_product_id = 1


print(
    "\nSản phẩm đang xem:"
)


product_test = products[
    products["ProductID"] == test_product_id
]


print(
    product_test[
        [
            "ProductID",
            "ProductName",
            "CategoryName",
            "BrandName",
            "MaterialName",
            "GemstoneName",
            "CollectionName"
        ]
    ]
)


print(
    "\nSản phẩm tương tự:"
)


content_result = recommend_content(
    test_product_id,
    5
)


print(content_result)


# ============================================================
# 8. TẠO USER - PRODUCT MATRIX
# ============================================================

print("\n==============================")
print("7. USER - PRODUCT MATRIX")
print("==============================")


# Chỉ lấy những đơn hàng có trạng thái không phải Đã hủy
if "Status" in orders.columns:

    valid_orders = orders[
        orders["Status"] != "Đã hủy"
    ]

else:

    valid_orders = orders.copy()


print(
    "Số đơn hàng hợp lệ:",
    len(valid_orders)
)


# Ghép orders với order_details
purchase_data = order_details.merge(
    valid_orders[
        [
            "OrderID",
            "CustomerID"
        ]
    ],
    on="OrderID",
    how="inner"
)


print(
    "\nDữ liệu mua hàng:"
)


print(
    purchase_data.head()
)


# ============================================================
# 9. TẠO MA TRẬN CUSTOMER - PRODUCT
# ============================================================

user_product = purchase_data.pivot_table(
    index="CustomerID",
    columns="ProductID",
    values="Quantity",
    aggfunc="sum",
    fill_value=0
)


print(
    "\nKích thước User-Product Matrix:"
)

print(
    user_product.shape
)


# ============================================================
# 10. COLLABORATIVE FILTERING
# ============================================================

def recommend_collaborative(
    customer_id,
    number=5
):

    # Kiểm tra customer
    if customer_id not in user_product.index:

        print(
            "Không tìm thấy CustomerID:",
            customer_id
        )

        return pd.DataFrame()


    # Lấy lịch sử mua của customer
    user_history = user_product.loc[
        customer_id
    ]


    # Tìm khách hàng tương tự
    user_similarity = cosine_similarity(
        user_product
    )


    customer_index = user_product.index.get_loc(
        customer_id
    )


    scores = user_similarity[
        customer_index
    ]


    similar_users = list(
        enumerate(scores)
    )


    similar_users = sorted(
        similar_users,
        key=lambda x: x[1],
        reverse=True
    )


    # Các sản phẩm khách hiện tại đã mua
    purchased_products = set(
        user_history[
            user_history > 0
        ].index
    )


    product_scores = {}


    # Lấy sản phẩm từ các khách hàng tương tự
    for user_index, user_score in similar_users[1:11]:

        # Bỏ similarity = 0
        if user_score <= 0:
            continue


        similar_customer = user_product.index[
            user_index
        ]


        similar_history = user_product.loc[
            similar_customer
        ]


        for product_id, quantity in similar_history.items():

            if quantity <= 0:
                continue


            # Không gợi ý sản phẩm đã mua
            if product_id in purchased_products:
                continue


            if product_id not in product_scores:

                product_scores[product_id] = 0


            product_scores[product_id] += (
                user_score * quantity
            )


    # Sắp xếp
    recommended_products = sorted(
        product_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )


    result = []


    for product_id, score in recommended_products:

        product_info = products[
            products["ProductID"] == product_id
        ]


        if product_info.empty:
            continue


        product_info = product_info.iloc[0]


        result.append(
            {
                "ProductID":
                    product_id,

                "ProductName":
                    product_info["ProductName"],

                "Category":
                    product_info["CategoryName"],

                "Brand":
                    product_info["BrandName"],

                "Material":
                    product_info["MaterialName"],

                "Gemstone":
                    product_info["GemstoneName"],

                "CollaborativeScore":
                    round(
                        float(score),
                        3
                    )
            }
        )


        if len(result) >= number:
            break


    return pd.DataFrame(result)


# ============================================================
# 11. TEST COLLABORATIVE FILTERING
# ============================================================

print("\n==============================")
print("8. TEST COLLABORATIVE FILTERING")
print("==============================")


# Lấy một customer bất kỳ
test_customer_id = user_product.index[0]


print(
    "Customer đang test:",
    test_customer_id
)


collaborative_result = recommend_collaborative(
    test_customer_id,
    5
)


print(
    "\nSản phẩm được gợi ý:"
)


print(
    collaborative_result
)


# ============================================================
# 12. HYBRID RECOMMENDATION
# ============================================================

def hybrid_recommendation(
    customer_id,
    product_id,
    number=5
):

    # --------------------------------
    # CONTENT
    # --------------------------------

    content_result = recommend_content(
        product_id,
        20
    )


    if content_result.empty:

        return pd.DataFrame()


    content_result = content_result.copy()


    # Chuẩn hóa Content score
    max_content = content_result[
        "Similarity"
    ].max()


    if max_content > 0:

        content_result[
            "ContentScore"
        ] = (
            content_result["Similarity"]
            / max_content
        )

    else:

        content_result[
            "ContentScore"
        ] = 0


    # --------------------------------
    # COLLABORATIVE
    # --------------------------------

    collaborative_result = recommend_collaborative(
        customer_id,
        20
    )


    if collaborative_result.empty:

        content_result[
            "CollaborativeScore"
        ] = 0

    else:

        collaborative_result = (
            collaborative_result[
                [
                    "ProductID",
                    "CollaborativeScore"
                ]
            ]
        )


        # Merge
        content_result = content_result.merge(
            collaborative_result,
            on="ProductID",
            how="left"
        )


        content_result[
            "CollaborativeScore"
        ] = (
            content_result[
                "CollaborativeScore"
            ]
            .fillna(0)
        )


        max_collaborative = (
            content_result[
                "CollaborativeScore"
            ].max()
        )


        if max_collaborative > 0:

            content_result[
                "CollaborativeScore"
            ] = (
                content_result[
                    "CollaborativeScore"
                ]
                / max_collaborative
            )


    # --------------------------------
    # HYBRID SCORE
    # --------------------------------

    content_weight = 0.6

    collaborative_weight = 0.4


    content_result[
        "HybridScore"
    ] = (

        content_result[
            "ContentScore"
        ]
        * content_weight

        +

        content_result[
            "CollaborativeScore"
        ]
        * collaborative_weight
    )


    # Sắp xếp
    content_result = content_result.sort_values(
        by="HybridScore",
        ascending=False
    )


    # Lấy top N
    content_result = content_result.head(
        number
    )


    return content_result[
        [
            "ProductID",
            "ProductName",
            "Category",
            "Brand",
            "Material",
            "Gemstone",
            "Similarity",
            "ContentScore",
            "CollaborativeScore",
            "HybridScore"
        ]
    ]


# ============================================================
# 13. TEST HYBRID
# ============================================================

print("\n==============================")
print("9. TEST HYBRID RECOMMENDATION")
print("==============================")


print(
    "Customer:",
    test_customer_id
)


print(
    "Product:",
    test_product_id
)


hybrid_result = hybrid_recommendation(
    test_customer_id,
    test_product_id,
    5
)


print(
    "\nKẾT QUẢ HYBRID:"
)


print(
    hybrid_result
)


# ============================================================
# 14. LƯU KẾT QUẢ RA CSV
# ============================================================

print("\n==============================")
print("10. LƯU KẾT QUẢ")
print("==============================")


content_result.to_csv(
    "../output/recommendation_content.csv",
    index=False,
    encoding="utf-8-sig"
)


if not collaborative_result.empty:

    collaborative_result.to_csv(
        "../output/recommendation_collaborative.csv",
        index=False,
        encoding="utf-8-sig"
    )


if not hybrid_result.empty:

    hybrid_result.to_csv(
        "../output/recommendation_hybrid.csv",
        index=False,
        encoding="utf-8-sig"
    )


print(
    "Đã lưu kết quả recommendation."
)


print("\n==============================")
print("HOÀN THÀNH")
print("==============================")