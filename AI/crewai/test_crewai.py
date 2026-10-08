from crew import run_crew


query = "Tìm cho tôi một chiếc vòng tay bằng vàng"


context = """
Sản phẩm:
- ProductID: 287
- Tên: Lắc tay Rose Gold
- Danh mục: Lắc tay
- Thương hiệu: SJC
- Chất liệu: Vàng 10K
- Đá quý: Emerald
- Bộ sưu tập: Minimal
- Giá bán chính xác: 10.898.911 VNĐ
- Tồn kho: 55

Sản phẩm:
- ProductID: 41
- Tên: Lắc tay Rose Gold
- Danh mục: Lắc tay
- Thương hiệu: SJC
- Chất liệu: Vàng 14K
- Đá quý: Sapphire
- Bộ sưu tập: Luxury
- Giá bán chính xác: 23.214.519 VNĐ
- Tồn kho: 23
"""


print("=" * 70)
print("TEST CREWAI")
print("=" * 70)

answer = run_crew(
    query,
    context
)

print()
print("=" * 70)
print("KẾT QUẢ")
print("=" * 70)

print(answer)