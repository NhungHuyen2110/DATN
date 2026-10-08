import pandas as pd


data=[

["SALE10",10],
["SALE20",20],
["VIP30",30]

]


df=pd.DataFrame(
data,
columns=[
"CouponCode",
"Discount"
]
)


df.to_csv(
"output/coupons.csv",
index=False
)
