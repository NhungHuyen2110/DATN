from crewai import Agent, LLM


# ======================================================
# TEST CREWAI AGENT + OLLAMA
# ======================================================

local_llm = LLM(
    model="ollama_chat/qwen2.5:3b",
    base_url="http://localhost:11434"
)


test_agent = Agent(
    role="Trợ lý AI",
    goal="Trả lời câu hỏi của người dùng bằng tiếng Việt",
    backstory="Bạn là một trợ lý AI chạy bằng Ollama Qwen2.5.",
    llm=local_llm,
    verbose=True,
    allow_delegation=False,
    max_iter=1
)


print("=" * 70)
print("TEST CREWAI AGENT + OLLAMA")
print("=" * 70)

question = "Hãy trả lời ngắn gọn: Qdrant dùng để làm gì?"

print("\nCâu hỏi:")
print(question)

print("\nAgent đang xử lý...\n")

try:
    result = test_agent.kickoff(question)

    print("\n" + "=" * 70)
    print("KẾT QUẢ")
    print("=" * 70)
    print(result)

except Exception as e:
    print("\n" + "=" * 70)
    print("LỖI")
    print("=" * 70)
    print(type(e).__name__)
    print(e)