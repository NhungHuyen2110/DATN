import pandas as pd

products = pd.read_csv("../output/products_ai.csv")

print(products.head())

from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

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
)

products["Vector"] = products["Text"].apply(
    lambda x: model.encode(x)
)

print(products["Text"].iloc[0])

print(len(products["Vector"].iloc[0]))

print(products["Vector"].iloc[0][:10])