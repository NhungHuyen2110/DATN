import pandas as pd
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient


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
print("Số order detail:", len(order_details))


# ============================================================
# 2. TẠO PRODUCT CONTENT
# ============================================================

print("\n==============================")
print("2. PRODUCT CONTENT")
print("==============================")


features = [
    "ProductName",
    "CategoryName",
    "BrandName",
    "MaterialName",
    "GemstoneName",
    "CollectionName"
]


products["content"] = (
    products[features]
    .fillna("")
    .astype(str)
    .agg(" ".join, axis=1)
)


# ============================================================
# 3. TF-IDF
# ============================================================

print("\n==============================")
print("3. TF-IDF")
print("==============================")


vectorizer = TfidfVectorizer(
    token_pattern=r"(?u)\b\w+\b"
)


product_matrix = vectorizer.fit_transform(
    products["content"]
)


tfidf_similarity = cosine_similarity(
    product_matrix
)


print(
    "TF-IDF matrix:",
    product_matrix.shape
)


# ============================================================
# 4. QDRANT
# ============================================================

print("\n==============================")
print("4. QDRANT")
print("==============================")


client = QdrantClient(
    host="localhost",
    port=6333
)


model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)


print("Đã kết nối Qdrant")


# ============================================================
# 5. TẠO USER - PRODUCT MATRIX
# ============================================================

print("\n==============================")
print("5. USER PRODUCT MATRIX")
print("==============================")


# Loại đơn hàng bị hủy

if "Status" in orders.columns:

    valid_orders = orders[
        orders["Status"] != "Đã hủy"
    ]

else:

    valid_orders = orders.copy()


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


user_product = purchase_data.pivot_table(
    index="CustomerID",
    columns="ProductID",
    values="Quantity",
    aggfunc="sum",
    fill_value=0
)


print(
    "User-Product matrix:",
    user_product.shape
)


# ============================================================
# 6. CONTENT RECOMMENDATION
# ============================================================

def get_content_scores(product_id):

    matched = products[
        products["ProductID"] == product_id
    ]


    if matched.empty:

        return {}


    index = matched.index[0]


    scores = tfidf_similarity[index]


    result = {}


    for i, score in enumerate(scores):

        pid = products.iloc[i]["ProductID"]


        if pid == product_id:
            continue


        result[pid] = float(score)


    return result


# ============================================================
# 7. QDRANT RECOMMENDATION
# ============================================================

def get_qdrant_scores(
    product_id,
    limit=30
):

    matched = products[
        products["ProductID"] == product_id
    ]


    if matched.empty:

        return {}


    content = matched.iloc[0]["content"]


    vector = model.encode(
        content
    ).tolist()


    search_result = client.query_points(
        collection_name="jewelry_products",
        query=vector,
        limit=limit + 5,
        with_payload=True
    )


    result = {}


    for point in search_result.points:

        if point.payload is None:
            continue


        pid = point.payload.get(
            "ProductID"
        )


        if pid is None:
            continue


        pid = int(pid)


        if pid == product_id:
            continue


        result[pid] = float(
            point.score
        )


    return result


# ============================================================
# 8. COLLABORATIVE FILTERING
# ============================================================

def get_collaborative_scores(
    customer_id
):

    if customer_id not in user_product.index:

        return {}


    customer_index = (
        user_product.index.get_loc(
            customer_id
        )
    )


    user_similarity = cosine_similarity(
        user_product
    )


    similarities = user_similarity[
        customer_index
    ]


    similar_users = list(
        enumerate(similarities)
    )


    similar_users = sorted(
        similar_users,
        key=lambda x: x[1],
        reverse=True
    )


    purchased = set(
        user_product.loc[
            customer_id
        ][
            lambda x: x > 0
        ].index
    )


    product_scores = {}


    # Lấy 10 khách hàng tương tự
    for user_index, similarity_score in similar_users[1:11]:

        if similarity_score <= 0:
            continue


        similar_customer = (
            user_product.index[
                user_index
            ]
        )


        history = user_product.loc[
            similar_customer
        ]


        for product_id, quantity in history.items():

            if quantity <= 0:
                continue


            if product_id in purchased:
                continue


            if product_id not in product_scores:

                product_scores[
                    product_id
                ] = 0


            product_scores[
                product_id
            ] += (
                similarity_score
                * quantity
            )


    return product_scores


# ============================================================
# 9. NORMALIZE SCORE
# ============================================================

def normalize_scores(scores):

    if not scores:
        return {}


    values = list(
        scores.values()
    )


    min_value = min(values)
    max_value = max(values)


    if max_value == min_value:

        return {
            key: 1
            for key in scores
        }


    result = {}


    for key, value in scores.items():

        result[key] = (
            value - min_value
        ) / (
            max_value - min_value
        )


    return result


# ============================================================
# 10. HYBRID RECOMMENDATION
# ============================================================

def hybrid_recommendation(
    customer_id,
    product_id,
    number=5
):

    print("\nĐang tạo recommendation...")


    # ---------------------------------------
    # CONTENT
    # ---------------------------------------

    content_scores = get_content_scores(
        product_id
    )


    # ---------------------------------------
    # QDRANT
    # ---------------------------------------

    qdrant_scores = get_qdrant_scores(
        product_id
    )


    # ---------------------------------------
    # COLLABORATIVE
    # ---------------------------------------

    collaborative_scores = (
        get_collaborative_scores(
            customer_id
        )
    )


    # ---------------------------------------
    # NORMALIZE
    # ---------------------------------------

    content_scores = normalize_scores(
        content_scores
    )


    qdrant_scores = normalize_scores(
        qdrant_scores
    )


    collaborative_scores = normalize_scores(
        collaborative_scores
    )


    # ---------------------------------------
    # TẤT CẢ PRODUCT
    # ---------------------------------------

    all_products = set()

    all_products.update(
        content_scores.keys()
    )

    all_products.update(
        qdrant_scores.keys()
    )

    all_products.update(
        collaborative_scores.keys()
    )


    # ---------------------------------------
    # HYBRID SCORE
    # ---------------------------------------

    results = []


    for pid in all_products:

        content_score = (
            content_scores.get(
                pid,
                0
            )
        )


        qdrant_score = (
            qdrant_scores.get(
                pid,
                0
            )
        )


        collaborative_score = (
            collaborative_scores.get(
                pid,
                0
            )
        )


        # -----------------------------------
        # TRỌNG SỐ
        # -----------------------------------

        hybrid_score = (

            0.30 * content_score

            +

            0.40 * qdrant_score

            +

            0.30 * collaborative_score

        )


        results.append(
            {
                "ProductID":
                    pid,

                "ContentScore":
                    round(
                        content_score,
                        4
                    ),

                "QdrantScore":
                    round(
                        qdrant_score,
                        4
                    ),

                "CollaborativeScore":
                    round(
                        collaborative_score,
                        4
                    ),

                "HybridScore":
                    round(
                        hybrid_score,
                        4
                    )
            }
        )


    result_df = pd.DataFrame(
        results
    )


    if result_df.empty:

        return result_df


    # ---------------------------------------
    # SORT
    # ---------------------------------------

    result_df = result_df.sort_values(
        "HybridScore",
        ascending=False
    )


    # ---------------------------------------
    # TOP N
    # ---------------------------------------

    result_df = result_df.head(
        number
    )


    # ---------------------------------------
    # JOIN PRODUCT INFO
    # ---------------------------------------

    result_df = result_df.merge(
        products[
            [
                "ProductID",
                "ProductName",
                "CategoryName",
                "BrandName",
                "MaterialName",
                "GemstoneName",
                "CollectionName",
                "SalePrice"
            ]
        ],
        on="ProductID",
        how="left"
    )


    return result_df[
        [
            "ProductID",
            "ProductName",
            "CategoryName",
            "BrandName",
            "MaterialName",
            "GemstoneName",
            "CollectionName",
            "SalePrice",
            "ContentScore",
            "QdrantScore",
            "CollaborativeScore",
            "HybridScore"
        ]
    ]


# ============================================================
# 11. TEST
# ============================================================

print("\n==============================")
print("6. TEST HYBRID")
print("==============================")


# Lấy customer đầu tiên có lịch sử mua hàng

test_customer_id = user_product.index[0]


# Sản phẩm test
test_product_id = 1


print(
    "Customer:",
    test_customer_id
)


print(
    "Product:",
    test_product_id
)


result = hybrid_recommendation(
    test_customer_id,
    test_product_id,
    5
)


print("\n==============================")
print("KẾT QUẢ HYBRID")
print("==============================")


print(result)


# ============================================================
# 12. LƯU FILE
# ============================================================

if not result.empty:

    result.to_csv(
        "../output/recommendation_hybrid_qdrant.csv",
        index=False,
        encoding="utf-8-sig"
    )


    print(
        "\nĐã lưu:"
    )

    print(
        "../output/recommendation_hybrid_qdrant.csv"
    )


print("\n==============================")
print("HOÀN THÀNH")
print("==============================")