import pandas as pd
import json

# Đọc products.csv
products = pd.read_csv("../output/products.csv")

print(products.head())

def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return pd.DataFrame(json.load(f))

categories = load_json("../data/categories.json")
brands = load_json("../data/brands.json")
materials = load_json("../data/materials.json")
gemstones = load_json("../data/gemstones.json")
collections = load_json("../data/collections.json")

print(categories.head())
print(brands.head())

def merge_lookup(products, lookup_df, id_column, new_name):
    lookup = lookup_df.rename(
        columns={
            "id": id_column,
            "name": new_name
        }
    )

    return products.merge(
        lookup,
        on=id_column,
        how="left"
    )

products = merge_lookup(
    products,
    categories,
    "CategoryID",
    "CategoryName"
)

products = merge_lookup(
    products,
    brands,
    "BrandID",
    "BrandName"
)

products = merge_lookup(
    products,
    materials,
    "MaterialID",
    "MaterialName"
)

products = merge_lookup(
    products,
    gemstones,
    "GemstoneID",
    "GemstoneName"
)

products = merge_lookup(
    products,
    collections,
    "CollectionID",
    "CollectionName"
)

print(
    products[
        [
            "ProductName",
            "CategoryName",
            "BrandName",
            "MaterialName",
            "GemstoneName",
            "CollectionName"
        ]
    ].head()
)

products.to_csv(
    "../output/products_ai.csv",
    index=False,
    encoding="utf-8-sig"
)

print("Đã tạo output/products_ai.csv")