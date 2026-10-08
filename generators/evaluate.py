import pandas as pd


orders=pd.read_csv(
"output/orders.csv"
)


print(
orders.CustomerID.nunique()
)
