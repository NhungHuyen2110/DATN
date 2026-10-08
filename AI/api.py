from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hybrid_recommendation import (
    hybrid_recommendation
)

import pandas as pd


# ============================================================
# 1. KHỞI TẠO FASTAPI
# ============================================================

app = FastAPI(
    title="Jewelry Recommendation API",
    description="API hệ thống gợi ý sản phẩm trang sức",
    version="1.0"
)


# ============================================================
# 2. CHO PHÉP WEBSITE GỌI API
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 3. ĐỌC PRODUCTS
# ============================================================

products = pd.read_csv(
    "../output/products_ai.csv"
)


# ============================================================
# 4. API HOME
# ============================================================

@app.get("/")
def home():

    return {
        "message": "Jewelry Recommendation API đang hoạt động"
    }


# ============================================================
# 5. LẤY DANH SÁCH SẢN PHẨM
# ============================================================

@app.get("/products")
def get_products():

    result = products[
        [
            "ProductID",
            "ProductName",
            "CategoryName",
            "BrandName",
            "MaterialName",
            "GemstoneName",
            "CollectionName",
            "SalePrice",
            "Stock"
        ]
    ].copy()


    return {
        "success": True,
        "number": len(result),
        "data": result.to_dict(
            orient="records"
        )
    }


# ============================================================
# 6. LẤY CHI TIẾT MỘT SẢN PHẨM
# ============================================================

@app.get("/products/{product_id}")
def get_product(product_id: int):

    result = products[
        products["ProductID"] == product_id
    ]


    if result.empty:

        return {
            "success": False,
            "message": "Không tìm thấy sản phẩm",
            "data": None
        }


    result = result[
        [
            "ProductID",
            "ProductName",
            "CategoryName",
            "BrandName",
            "MaterialName",
            "GemstoneName",
            "CollectionName",
            "SalePrice",
            "Stock"
        ]
    ]


    return {
        "success": True,
        "data": result.iloc[0].to_dict()
    }


# ============================================================
# 7. RECOMMENDATION
# ============================================================

@app.get("/recommendations")
def recommendations(
    customer_id: str,
    product_id: int,
    number: int = 5
):

    result = hybrid_recommendation(
        customer_id,
        product_id,
        number
    )


    if result.empty:

        return {
            "success": False,
            "message": "Không tìm thấy sản phẩm gợi ý",
            "data": []
        }


    return {
        "success": True,
        "customer_id": customer_id,
        "product_id": product_id,
        "number": len(result),
        "data": result.to_dict(
            orient="records"
        )
    }