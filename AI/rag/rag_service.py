from fastapi import FastAPI
from crewai.retrieval import (
    hybrid_search,
    build_rag_context
)
from crewai.crew import run_crew

from pydantic import BaseModel, Field

app = FastAPI()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@app.post("/chat")
def chat(request: ChatRequest):
    return answer_jewelry_question(
        request.message
    )

def answer_jewelry_question(query, top_k=3):
    products = hybrid_search(
        query,
        top_k=top_k
    )

    if not products:
        return {
            "success": True,
            "answer": "Không tìm thấy sản phẩm phù hợp.",
            "products": []
        }

    context = build_rag_context(products)

    answer = run_crew(
        query,
        context
    )

    return {
        "success": True,
        "answer": answer,
        "products": products
    }