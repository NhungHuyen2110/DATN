from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

client = QdrantClient(
    host="localhost",
    port=6333
)

print("Đã kết nối")

model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

print("Đã load model")

query = input("Nhập sản phẩm cần tìm: ")

print(query)

query_vector = model.encode(query)

print(query_vector)

print(len(query_vector))

query_vector = model.encode(query).tolist()

print(type(query_vector))