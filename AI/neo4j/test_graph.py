from graph_queries import (
    get_product,
    get_products,
    search_products_by_attributes,
    get_customer_history
)


print("=" * 70)
print("TEST KNOWLEDGE GRAPH")
print("=" * 70)


# =========================================================
# TEST 1
# =========================================================

print("\n")
print("=" * 70)
print("TEST 1 - PRODUCT ID 1")
print("=" * 70)

product = get_product(1)

print(product)


# =========================================================
# TEST 2
# =========================================================

print("\n")
print("=" * 70)
print("TEST 2 - NHIEU PRODUCT")
print("=" * 70)

products = get_products([
    1,
    2,
    3,
    4,
    5
])

for product in products:

    print(product)


# =========================================================
# TEST 3
# =========================================================

print("\n")
print("=" * 70)
print("TEST 3 - TIM THEO THUOC TINH")
print("=" * 70)

products = search_products_by_attributes(
    category="Bông tai",
    gemstone="Moissanite",
    collection="Minimal"
)

print("So ket qua:", len(products))

for product in products[:10]:

    print(product)


# =========================================================
# TEST 4
# =========================================================

print("\n")
print("=" * 70)
print("TEST 4 - LICH SU KHACH HANG")
print("=" * 70)

history = get_customer_history(
    "KH00001"
)

print("So ban ghi:", len(history))

for item in history[:10]:

    print(item)


print("\n")
print("=" * 70)
print("TEST GRAPH HOAN TAT")
print("=" * 70)