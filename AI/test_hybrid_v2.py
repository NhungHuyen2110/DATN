from hybrid_recommendation_v2 import recommend_v2

result = recommend_v2(
    customer_id="KH01926",
    product_id=1,
    top_k=5
)

for item in result:
    print(item)