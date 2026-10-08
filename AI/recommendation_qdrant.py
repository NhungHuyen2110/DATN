import pandas as pd

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient


# ============================================================
# 1. KẾT NỐI QDRANT
# ============================================================

print("==============================")
print("1. KẾT NỐI QDRANT")
print("==============================")


client = QdrantClient(
    host="localhost",
    port=6333
)


print("Đã kết nối Qdrant!")


# ============================================================
# 2. LOAD MODEL
# ============================================================

print("\n==============================")
print("2. LOAD MODEL")
print("==============================")


model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)


print("Đã load model!")


# ============================================================
# 3. ĐỌC PRODUCTS_AI
# ============================================================

print("\n==============================")
print("3. ĐỌC DỮ LIỆU")
print("==============================")


products = pd.read_csv(
    "../output/products_ai.csv"
)


print(
    "Số sản phẩm:",
    len(products)
)


# ============================================================
# 4. TẠO PRODUCT CONTENT
# ============================================================

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


print("\nVí dụ content:")

print(
    products[
        [
            "ProductID",
            "content"
        ]
    ].head()
)


# ============================================================
# 5. TÌM SẢN PHẨM TRONG QDRANT
# ============================================================

def recommend_qdrant(
    product_id,
    number=5
):

    product = products[
        products["ProductID"] == product_id
    ]


    if product.empty:

        print(
            "Không tìm thấy ProductID:",
            product_id
        )

        return pd.DataFrame()


    content = product.iloc[0]["content"]


    # ========================================
    # TẠO EMBEDDING
    # ========================================

    vector = model.encode(
        content
    ).tolist()


    # ========================================
    # SEARCH QDRANT
    # ========================================

    search_result = client.query_points(
        collection_name="jewelry_products",
        query=vector,
        limit=number + 10,
        with_payload=True
    )


    result = []


    for point in search_result.points:

        payload = point.payload


        if payload is None:
            continue


        result.append(
            {
                "ProductID":
                    payload.get(
                        "ProductID"
                    ),

                "ProductName":
                    payload.get(
                        "ProductName"
                    ),

                "Category":
                    payload.get(
                        "CategoryName"
                    ),

                "Brand":
                    payload.get(
                        "BrandName"
                    ),

                "Material":
                    payload.get(
                        "MaterialName"
                    ),

                "Gemstone":
                    payload.get(
                        "GemstoneName"
                    ),

                "Collection":
                    payload.get(
                        "CollectionName"
                    ),

                "Score":
                    round(
                        float(point.score),
                        4
                    )
            }
        )


    result_df = pd.DataFrame(
        result
    )


    # Loại chính sản phẩm đang xem
    result_df = result_df[
        result_df["ProductID"] != product_id
    ]


    return result_df.head(
        number
    )


# ============================================================
# 6. TEST
# ============================================================

print("\n==============================")
print("4. QDRANT RECOMMENDATION")
print("==============================")


test_product_id = 1


print(
    "Sản phẩm đang xem:",
    test_product_id
)


result = recommend_qdrant(
    test_product_id,
    5
)


print("\nSản phẩm được gợi ý:")

print(result)


# ============================================================
# 7. LƯU KẾT QUẢ
# ============================================================

if not result.empty:

    result.to_csv(
        "../output/recommendation_qdrant.csv",
        index=False,
        encoding="utf-8-sig"
    )


    print(
        "\nĐã lưu:"
    )

    print(
        "../output/recommendation_qdrant.csv"
    )