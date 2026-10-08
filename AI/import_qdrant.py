import pandas as pd

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient

from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct
)

products = pd.read_csv("../output/products_ai.csv")

print("Số sản phẩm:", len(products))

client = QdrantClient(
    host="localhost",
    port=6333
)

print("Đã kết nối Qdrant")

model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

print("Đã load model")

if client.collection_exists("jewelry_products"):
    client.delete_collection("jewelry_products")

client.create_collection(
    collection_name="jewelry_products",
    vectors_config=VectorParams(
        size=384,
        distance=Distance.COSINE
    )
)

print("Đã tạo Collection")

products["Text"] = (
    products["ProductName"].astype(str)
    + ". Danh mục: "
    + products["CategoryName"].astype(str)
    + ". Thương hiệu: "
    + products["BrandName"].astype(str)
    + ". Chất liệu: "
    + products["MaterialName"].astype(str)
    + ". Đá: "
    + products["GemstoneName"].astype(str)
    + ". Bộ sưu tập: "
    + products["CollectionName"].astype(str)
)

products["Vector"] = products["Text"].apply(
    lambda x: model.encode(x).tolist()
)

print("Đã tạo Vector")

points = []

for _, row in products.iterrows():

    point = PointStruct(
        id=int(row["ProductID"]),
        vector=row["Vector"],
        payload={
            "ProductID": int(row["ProductID"]),
            "ProductName": row["ProductName"],
            "Category": row["CategoryName"],
            "Brand": row["BrandName"],
            "Material": row["MaterialName"],
            "Gemstone": row["GemstoneName"],
            "Collection": row["CollectionName"],
            "Price": float(row["SalePrice"])
        }
    )

    points.append(point)

print("Đã tạo", len(points), "Point")

client.upsert(
    collection_name="jewelry_products",
    points=points
)

print("Đã import", len(points), "sản phẩm vào Qdrant")