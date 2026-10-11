from crewai import Agent, LLM

from tools import QdrantSearchTool


# ======================================================
# 1. LOCAL LLM - OLLAMA
# ======================================================

local_llm = LLM(
    model="ollama_chat/qwen2.5:3b",
    base_url="http://localhost:11434"
)


# ======================================================
# 2. QDRANT TOOL
# ======================================================

qdrant_tool = QdrantSearchTool()


# ======================================================
# 3. AGENT
# ======================================================

product_search_agent = Agent(
    role="Chuyên gia tìm kiếm sản phẩm trang sức",

    goal=(
        "Tìm sản phẩm trang sức phù hợp với yêu cầu "
        "của khách hàng bằng Qdrant."
    ),

    backstory=(
        "Bạn là chuyên gia tìm kiếm sản phẩm trang sức. "
        "Bạn sử dụng Qdrant để tìm kiếm sản phẩm dựa "
        "trên semantic search. "
        "Bạn chỉ sử dụng dữ liệu thực tế được Qdrant trả về."
    ),

    tools=[qdrant_tool],

    llm=local_llm,

    verbose=True,

    allow_delegation=False,

    max_iter=1
)


# ======================================================
# 4. TEST
# ======================================================

print("=" * 70)
print("TEST CREWAI AGENT + QDRANT")
print("=" * 70)

question = "Tìm cho tôi một chiếc vòng tay bằng vàng"

print("\nCâu hỏi:")
print(question)

print("\nAgent đang tìm kiếm...\n")


try:

    result = product_search_agent.kickoff(
        f"""
Khách hàng hỏi:

{question}

Hãy sử dụng Qdrant Product Search Tool để tìm
tối đa 5 sản phẩm phù hợp.

Sau khi Qdrant trả về kết quả:
- Không tự tạo sản phẩm.
- Không tự tạo ProductID.
- Không tự tạo giá.
- Chỉ sử dụng dữ liệu Qdrant trả về.

Hãy trả về danh sách sản phẩm tìm được.
"""
    )

    print("\n" + "=" * 70)
    print("KẾT QUẢ QDRANT AGENT")
    print("=" * 70)

    print(result)

except Exception as e:

    print("\n" + "=" * 70)
    print("LỖI")
    print("=" * 70)

    print(type(e).__name__)
    print(e)