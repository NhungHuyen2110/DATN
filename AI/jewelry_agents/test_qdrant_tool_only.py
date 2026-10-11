from tools import QdrantSearchTool


print("=" * 60)
print("TEST QDRANT TOOL ĐỘC LẬP")
print("=" * 60)

tool = QdrantSearchTool()

result = tool._run(
    query="Tìm cho tôi một chiếc vòng tay bằng vàng",
    top_k=5
)

print("\n" + "=" * 60)
print("KẾT QUẢ QDRANT")
print("=" * 60)

print(result)

print("\n" + "=" * 60)
print("TEST HOÀN TẤT")
print("=" * 60)