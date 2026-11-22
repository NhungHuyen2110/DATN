from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Header
from pydantic import BaseModel, Field
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.rag_service import answer_jewelry_question

import pandas as pd
from functools import lru_cache
from contextlib import asynccontextmanager
import logging
import os
import hmac
from shared.observability import install as install_observability


@asynccontextmanager
async def lifespan(app):
    if os.getenv('LUMIERE_MODEL_WARMUP_ENABLED','false').lower()=='true':
        import threading
        def warm_model():
            try:
                from jewelry_agents import retrieval
                retrieval.warm_shopping_model()
            except Exception as exc:
                logging.getLogger('uvicorn.error').info('Optional model warmup: %s',type(exc).__name__)
        threading.Thread(target=warm_model,name='lumiere-model-warmup',daemon=True).start()
    yield
    from jewelry_agents import retrieval
    retrieval.close_retrieval_limits()
    for client in (retrieval.qdrant_client, retrieval.neo4j_driver):
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                logging.getLogger('uvicorn.error').warning('AI client shutdown error: %s', type(exc).__name__)

# ============================================================
# 1. KHỞI TẠO FASTAPI
# ============================================================

app = FastAPI(
    title="Jewelry Recommendation API",
    description="API hệ thống gợi ý sản phẩm trang sức",
    version="1.0",
    lifespan=lifespan
)
install_observability(app, 'ai-api')


@app.get("/recommendations/v2")
def recommendations_v2(
    customer_id: str,
    product_id: int,
    number: int = 5
):
    if os.getenv('LUMIERE_PUBLIC_RECOMMENDATIONS_V2_ENABLED', 'true').lower() == 'true':
        return public_recommendation_response(customer_id, product_id, number)
    products = load_products()
    # Kiểm tra ProductID có tồn tại hay không
    if product_id not in products["ProductID"].values:
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

    try:
        from hybrid_recommendation_v2 import recommend_v2
        result = recommend_v2(customer_id=customer_id, product_id=product_id, top_k=number)
    except Exception:
        raise HTTPException(status_code=503, detail="Dịch vụ gợi ý tạm thời chưa sẵn sàng") from None

    return {
        "success": True,
        "customer_id": customer_id,
        "product_id": product_id,
        "number": len(result),
        "data": [{key: value for key, value in item.items() if not key.endswith("Score")} for item in result]
    }

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

@lru_cache(maxsize=1)
def load_products():
    return pd.read_csv(Path(__file__).resolve().parents[1] / "output/products_ai.csv")


# ============================================================
# 4. API HOME
# ============================================================

@app.get("/")
def home():

    return {
        "message": "Jewelry Recommendation API đang hoạt động"
    }


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    from jewelry_agents.business_catalog import fetch_catalog
    try:
        fetch_catalog()
    except Exception:
        raise HTTPException(status_code=503, detail="Business catalog unavailable") from None
    return {"status": "ready", "optional_sources": ["qdrant", "neo4j", "ollama"]}


# ============================================================
# 5. LẤY DANH SÁCH SẢN PHẨM
# ============================================================

@app.get("/products")
def get_products():
    products = load_products()
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
    products = load_products()
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
    if os.getenv('LUMIERE_PUBLIC_RECOMMENDATIONS_V2_ENABLED', 'true').lower() == 'true':
        return public_recommendation_response(customer_id, product_id, number)
    if not 1 <= number <= 20:
        raise HTTPException(status_code=422, detail="number phải từ 1 đến 20")
    try:
        from hybrid_recommendation import hybrid_recommendation
        result = hybrid_recommendation(customer_id, product_id, number)
    except Exception:
        raise HTTPException(status_code=503, detail="Dịch vụ gợi ý tạm thời chưa sẵn sàng") from None


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


def public_recommendation_response(customer_id, product_id, number):
    if not 1 <= number <= 20:
        raise HTTPException(status_code=422, detail='number phải từ 1 đến 20')
    from jewelry_agents.public_recommendation import recommend_public
    try:
        data, degraded = recommend_public(product_id, number)
    except LookupError:
        raise HTTPException(status_code=404, detail='Không xác minh được sản phẩm tham chiếu hiện tại') from None
    except Exception:
        raise HTTPException(status_code=503, detail='Dịch vụ gợi ý tạm thời chưa sẵn sàng') from None
    return {'success': True, 'customer_id': customer_id, 'product_id': product_id,
            'number': len(data), 'data': data, 'personalized': False,
            'status': 'degraded' if degraded else 'ok'}

# =====================================================
# CHATBOT RAG + CREWAI
# =====================================================

class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)
    conversation_id: str | None = Field(default=None,max_length=128)


class DiagnosticsRequest(ChatRequest):
    rerank: bool = False
    semantic_entities: bool = False


@app.post('/internal/retrieval-diagnostics', include_in_schema=False)
def retrieval_diagnostics(request: DiagnosticsRequest, authorization: str | None = Header(default=None)):
    token = os.getenv('LUMIERE_AI_DIAGNOSTICS_TOKEN', '')
    if not token or not hmac.compare_digest((authorization or '').encode(), ('Bearer ' + token).encode()):
        raise HTTPException(status_code=404, detail='Not found')
    from jewelry_agents import retrieval
    from jewelry_agents.business_catalog import fetch_catalog
    from jewelry_agents.search_service import search, RetrievalUnavailable
    from jewelry_agents.reranking import GraphFeatureReranker
    try:
        encoder = retrieval.get_dense_services()[1] if request.semantic_entities else None
        return search(request.query, request.top_k, dense=retrieval.search_qdrant, catalog=fetch_catalog,
                      parse_price=retrieval.extract_price_filter, graph=retrieval.graph_search_candidates,
                      graph_expander=retrieval.graph_expand_candidates,
                      reranker=GraphFeatureReranker() if request.rerank else None,
                      entity_encoder=encoder, diagnostics=True)
    except RetrievalUnavailable:
        raise HTTPException(status_code=503, detail='Authoritative catalog unavailable') from None
    except ValueError:
        raise HTTPException(status_code=422, detail='Invalid diagnostic query or ranking contract') from None
    except Exception:
        raise HTTPException(status_code=503, detail='Diagnostic source temporarily unavailable') from None


@app.post("/chat", tags=["Chatbot RAG"])
def chat(request: ChatRequest):
    from shared.conversation import converse
    return converse(request.query,request.conversation_id,('customer-public',),
                    lambda query:answer_jewelry_question(query=query,top_k=request.top_k))
