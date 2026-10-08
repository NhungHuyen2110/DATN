import pandas as pd
from pathlib import Path


# =========================================================
# XÁC ĐỊNH THƯ MỤC PROJECT
# =========================================================

# check_data.py nằm tại:
# D:\JewelryDatasetGenerator\AI\neo4j\check_data.py

CURRENT_FILE = Path(__file__).resolve()

# neo4j -> AI -> JewelryDatasetGenerator
PROJECT_DIR = CURRENT_FILE.parents[2]

# Thư mục output
OUTPUT_DIR = PROJECT_DIR / "output"


# =========================================================
# CÁC FILE CẦN KIỂM TRA
# =========================================================

FILES = [
    "products_ai.csv",
    "customers.csv",
    "orders.csv",
    "order_details.csv"
]


# =========================================================
# HIỂN THỊ ĐƯỜNG DẪN
# =========================================================

print("=" * 70)
print("KIEM TRA DU LIEU CSV")
print("=" * 70)

print("Project:")
print(PROJECT_DIR)

print("\nThu muc output:")
print(OUTPUT_DIR)


# =========================================================
# KIỂM TRA TỪNG FILE
# =========================================================

for filename in FILES:

    filepath = OUTPUT_DIR / filename

    print("\n")
    print("=" * 70)
    print(f"FILE: {filename}")
    print("=" * 70)

    # -----------------------------------------------------
    # Kiểm tra file tồn tại
    # -----------------------------------------------------

    if not filepath.exists():

        print("KHONG TIM THAY FILE:")
        print(filepath)

        continue

    # -----------------------------------------------------
    # Đọc CSV
    # -----------------------------------------------------

    try:

        df = pd.read_csv(filepath)

    except Exception as e:

        print("LOI KHI DOC FILE:")
        print(e)

        continue

    # -----------------------------------------------------
    # Thông tin file
    # -----------------------------------------------------

    print("Duong dan:")
    print(filepath)

    print("\nSo dong:", len(df))

    print("\nSo cot:", len(df.columns))

    print("\nCac cot:")

    for column in df.columns:

        print(" -", column)

    # -----------------------------------------------------
    # 5 dòng đầu
    # -----------------------------------------------------

    print("\n5 dong dau:")

    print(df.head().to_string(index=False))


# =========================================================
# KẾT THÚC
# =========================================================

print("\n")
print("=" * 70)
print("HOAN THANH KIEM TRA DU LIEU")
print("=" * 70)