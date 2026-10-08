import sys
import os

# Tìm đường dẫn đến thư mục gốc (JewelryDatasetGenerator) và thêm vào hệ thống
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Sau đó mới import module
from utils.file_helper import load_json
import pandas as pd

def generate_categories():
    # 1. Đọc dữ liệu từ file JSON cấu hình
    categories_data = load_json("data/categories.json")

    # 2. Chuyển đổi thành DataFrame của Pandas
    df = pd.DataFrame(categories_data)

    # Nếu file JSON của bạn dùng key là 'id' và 'name', đổi tên cột cho đúng chuẩn Database
    if "id" in df.columns and "name" in df.columns:
        df = df.rename(columns={"id": "CategoryID", "name": "CategoryName"})

    # 3. Xuất ra file CSV trong thư mục output
    df.to_csv(
        "output/categories.csv",
        index=False,
        encoding="utf-8-sig"  # Giúp Excel hiển thị đúng tiếng Việt không bị lỗi font
    )

    print("=" * 50)
    print("CATEGORY: Tạo categories.csv thành công!")
    print("=" * 50)

    return df

if __name__ == "__main__":
    generate_categories()