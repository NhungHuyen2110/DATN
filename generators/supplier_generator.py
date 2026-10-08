import os
import sys
import pandas as pd

# Thêm thư mục gốc vào path để import được module 'utils' không bị lỗi
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.file_helper import load_json


def generate_suppliers():
    # 1. Đọc dữ liệu từ file JSON cấu hình
    suppliers_data = load_json("data/suppliers.json")

    # 2. Chuyển đổi thành DataFrame của Pandas
    df = pd.DataFrame(suppliers_data)

    # 3. Chuẩn hóa tên cột (nếu file JSON dùng key viết thường như 'id', 'name', 'address')
    rename_mapping = {}
    if "id" in df.columns:
        rename_mapping["id"] = "SupplierID"
    if "name" in df.columns:
        rename_mapping["name"] = "SupplierName"
    if "address" in df.columns:
        rename_mapping["address"] = "Address"

    if rename_mapping:
        df = df.rename(columns=rename_mapping)

    # 4. Đảm bảo thư mục output tồn tại và lưu file CSV
    os.makedirs("output", exist_ok=True)
    output_path = os.path.join("output", "suppliers.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 50)
    print("SUPPLIER: Tạo output/suppliers.csv thành công!")
    print("=" * 50)

    return df


if __name__ == "__main__":
    generate_suppliers()