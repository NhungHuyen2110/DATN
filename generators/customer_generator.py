import pandas as pd
import random
from faker import Faker


fake = Faker('vi_VN')


# số lượng khách hàng
NUM_CUSTOMERS = 2000


# danh sách dữ liệu giả
genders = [
    "Nam",
    "Nữ"
]


cities = [
    "TP.HCM",
    "Hà Nội",
    "Đà Nẵng",
    "Cần Thơ",
    "Bình Dương",
    "Đồng Nai"
]


jobs = [
    "Sinh viên",
    "Nhân viên văn phòng",
    "Kinh doanh",
    "Giáo viên",
    "Kỹ sư",
    "Quản lý"
]


categories = [
    "Nhẫn",
    "Dây chuyền",
    "Bông tai",
    "Vòng tay",
    "Lắc chân",
    "Kim cương"
]


frequency = [
    "Hiếm khi",
    "1 lần/năm",
    "2-3 lần/năm",
    "Hàng tháng"
]


levels = [
    "Bronze",
    "Silver",
    "Gold",
    "Diamond"
]



customers=[]


for i in range(1, NUM_CUSTOMERS+1):

    customer = {

        "CustomerID":
            f"KH{i:05d}",


        "FullName":
            fake.name(),


        "Gender":
            random.choice(genders),


        "Age":
            random.randint(18,60),


        "City":
            random.choice(cities),


        "Job":
            random.choice(jobs),


        "Income":
            random.randint(
                5000000,
                50000000
            ),


        "FavoriteCategory":
            random.choice(categories),


        "Budget":
            random.randint(
                1000000,
                50000000
            ),


        "ShoppingFrequency":
            random.choice(frequency),


        "MemberLevel":
            random.choice(levels)

    }


    customers.append(customer)



# tạo dataframe

df = pd.DataFrame(customers)



# xuất file csv

df.to_csv(
    "output/customers.csv",
    index=False,
    encoding="utf-8-sig"
)



print(
    "Đã tạo",
    NUM_CUSTOMERS,
    "khách hàng"
)


print(df.head())
