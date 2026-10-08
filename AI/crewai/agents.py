from crewai import Agent, LLM


# ============================================================
# LOCAL QWEN 3B
# ============================================================

local_llm = LLM(
    model="ollama_chat/qwen2.5:3b",
    base_url="http://localhost:11434"
)


# ============================================================
# JEWELRY RECOMMENDATION AGENT
# ============================================================

jewelry_agent = Agent(
    role="Trợ lý tư vấn trang sức",
    
    goal=(
        "Tư vấn sản phẩm trang sức dựa trên dữ liệu "
        "được cung cấp từ hệ thống Hybrid Retrieval."
    ),

    backstory=(
        "Bạn là một trợ lý tư vấn trang sức. "
        "Bạn chỉ được sử dụng thông tin sản phẩm được cung cấp "
        "trong context. Không được tự tạo sản phẩm, ProductID, "
        "giá bán hoặc thông tin không có trong dữ liệu."
    ),

    llm=local_llm,

    verbose=True,

    allow_delegation=False
)