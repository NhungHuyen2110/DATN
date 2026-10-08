import pandas as pd

# Đọc file products.csv
df = pd.read_csv("../output/products.csv")

# Hiển thị 5 dòng đầu
print(df.head())

# Số lượng sản phẩm
print("\nSố sản phẩm:", len(df))

# Danh sách cột
print("\nTên các cột:")
print(df.columns)

# Kiểm tra dữ liệu thiếu
print("\nDữ liệu thiếu:")
print(df.isnull().sum())

# In thử sản phẩm đầu tiên
print("\nSản phẩm đầu tiên:")
print(df.iloc[0])