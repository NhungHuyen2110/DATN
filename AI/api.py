from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel, Field

import os


def answer_jewelry_question(query, top_k=3):
    if os.getenv("AI_PIPELINE", "legacy") == "modular":
        from lumiere.bootstrap import answer_service
        from lumiere.understanding import QueryError
        try:
            with answer_service(app.state.embedding_provider) as service:
                return service.answer(query, top_k)
        except QueryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except Exception:
            raise HTTPException(status_code=503, detail="Dịch vụ tư vấn tạm thời không khả dụng") from None
    from rag.rag_service import answer_jewelry_question as legacy_answer
    return legacy_answer(query, top_k)


def hybrid_recommendation(*args):
    from hybrid_recommendation import hybrid_recommendation as legacy_recommend
    return legacy_recommend(*args)


def recommend_v2(**kwargs):
    from hybrid_recommendation_v2 import recommend_v2 as legacy_recommend
    return legacy_recommend(**kwargs)

# ============================================================
# 1. KHỞI TẠO FASTAPI
# ============================================================

app = FastAPI(
    title="Jewelry Recommendation API",
    description="API hệ thống gợi ý sản phẩm trang sức",
    version="1.0"
)
from lumiere.bootstrap import SemanticModelProvider
app.state.embedding_provider = SemanticModelProvider()


@app.get("/recommendations/v2")
def recommendations_v2(
    customer_id: str,
    product_id: int,
    number: int = 5
):
    # Kiểm tra ProductID có tồn tại hay không
    if not any(row["ProductID"] == product_id for row in catalog_rows()):
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy sản phẩm có ID {product_id}"
        )

    # Kiểm tra số lượng sản phẩm gợi ý
    if number < 1 or number > 20:
        raise HTTPException(
            status_code=422,
            detail="number phải nằm trong khoảng từ 1 đến 20"
        )

    result = recommend_v2(
        customer_id=customer_id,
        product_id=product_id,
        top_k=number
    )

    return {
        "success": True,
        "customer_id": customer_id,
        "product_id": product_id,
        "number": len(result),
        "data": result
    }

# ============================================================
# 2. CHO PHÉP WEBSITE GỌI API
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("AI_CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 3. ĐỌC PRODUCTS
# ============================================================

def catalog_rows():
    from lumiere.bootstrap import catalog_repository
    return [{"ProductID": p.id, "ProductName": p.name, "CategoryName": p.category,
             "BrandName": p.brand, "MaterialName": p.material, "GemstoneName": p.gemstone,
             "CollectionName": p.collection, "SalePrice": float(p.price), "Stock": p.stock}
            for p in catalog_repository().all()]


@app.get("/health", include_in_schema=False)
@app.get("/health/live", include_in_schema=False)
def health():
    return {"status": "alive", "pipeline": os.getenv("AI_PIPELINE", "legacy")}


@app.get("/health/ready", include_in_schema=False)
def ready():
    from fastapi.responses import JSONResponse
    from lumiere.health import readiness
    result = readiness(app.state.embedding_provider)
    return JSONResponse(result, status_code=200 if result["status"] == "ready" else 503)


@app.get("/metrics", include_in_schema=False)
def metrics():
    from fastapi.responses import PlainTextResponse
    from lumiere.metrics import render
    return PlainTextResponse(render(), media_type="text/plain; version=0.0.4")


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

    result = catalog_rows()
    return {"success": True, "number": len(result), "data": result}


# ============================================================
# 6. LẤY CHI TIẾT MỘT SẢN PHẨM
# ============================================================

@app.get("/products/{product_id}")
def get_product(product_id: int):

    result = next((row for row in catalog_rows() if row["ProductID"] == product_id), None)
    if result is None:
        return {"success": False, "message": "Không tìm thấy sản phẩm", "data": None}
    return {"success": True, "data": result}


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

# =====================================================
# CHATBOT RAG + CREWAI
# =====================================================

class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


@app.post("/chat", tags=["Chatbot RAG"])
def chat(request: ChatRequest):
    top_k = request.top_k
    if os.getenv("AI_PIPELINE", "legacy") == "modular" and "top_k" not in request.model_fields_set:
        from lumiere.understanding import requested_top_k
        requested = requested_top_k(request.query)
        if requested is not None:
            if not 1 <= requested <= 10:
                raise HTTPException(status_code=422, detail="top_k phải nằm trong khoảng từ 1 đến 10")
            top_k = requested
    result = answer_jewelry_question(
        query=request.query,
        top_k=top_k
    )
    from lumiere.metrics import record_chat
    record_chat(result)
    return result
