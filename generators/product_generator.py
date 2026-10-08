import pandas as pd
import random
import os

from utils.file_helper import load_json
from utils.random_helper import *

def generate_products():

    categories = load_json("data/categories.json")
    brands = load_json("data/brands.json")
    materials = load_json("data/materials.json")
    gemstones = load_json("data/gemstones.json")
    collections = load_json("data/collections.json")
    names = load_json("data/product_names.json")

    products=[]

    for i in range(1,501):

        category=random_choice(categories)
        brand=random_choice(brands)
        material=random_choice(materials)
        gemstone=random_choice(gemstones)
        collection=random_choice(collections)

        product_name=random.choice(names)

        cost=random_price()

        sale=int(cost*1.3)

        wholesale=int(cost*1.15)

        product={

            "ProductID":i,

            "SKU":f"SP{i:06}",

            "Barcode":f"893{i:09}",

            "ProductName":f"{category['name']} {product_name}",

            "CategoryID":category["id"],

            "BrandID":brand["id"],

            "MaterialID":material["id"],

            "GemstoneID":gemstone["id"],

            "CollectionID":collection["id"],

            "Weight":random_weight(),

            "SalePrice":sale,

            "WholesalePrice":wholesale,

            "CostPrice":cost,

            "Stock":random_stock()

        }

        products.append(product)

    df=pd.DataFrame(products)

    os.makedirs("output",exist_ok=True)

    df.to_csv("output/products.csv",
              index=False,
              encoding="utf-8-sig")

    df.to_json("output/products.json",
               orient="records",
               force_ascii=False,
               indent=4)

    print("Product Generated :",len(products))

    return products