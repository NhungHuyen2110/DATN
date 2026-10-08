import pandas as pd
from pathlib import Path
from neo4j import GraphDatabase


# =========================================================
# 1. CẤU HÌNH
# =========================================================

URI = "neo4j://127.0.0.1:7687"

USERNAME = "neo4j"

PASSWORD = "12345678"


# =========================================================
# 2. XÁC ĐỊNH THƯ MỤC PROJECT
# =========================================================

CURRENT_FILE = Path(__file__).resolve()

# import_data.py:
# D:\JewelryDatasetGenerator\AI\neo4j\import_data.py

PROJECT_DIR = CURRENT_FILE.parents[2]

OUTPUT_DIR = PROJECT_DIR / "output"


# =========================================================
# 3. ĐƯỜNG DẪN CÁC FILE CSV
# =========================================================

PRODUCT_FILE = OUTPUT_DIR / "products_ai.csv"
CUSTOMER_FILE = OUTPUT_DIR / "customers.csv"
ORDER_FILE = OUTPUT_DIR / "orders.csv"
ORDER_DETAIL_FILE = OUTPUT_DIR / "order_details.csv"


# =========================================================
# 4. KẾT NỐI NEO4J
# =========================================================

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)


# =========================================================
# 5. HÀM CHẠY QUERY
# =========================================================

def run_query(query, parameters=None):

    with driver.session() as session:

        result = session.run(
            query,
            parameters or {}
        )

        return result.consume()


# =========================================================
# 6. IMPORT CATEGORY
# =========================================================

def import_categories(products):

    print("\n[1/9] IMPORT CATEGORY")

    data = (
        products[
            ["CategoryID", "CategoryName"]
        ]
        .drop_duplicates()
        .to_dict("records")
    )

    query = """
    UNWIND $rows AS row

    MERGE (c:Category {
        category_id: toInteger(row.CategoryID)
    })

    SET c.name = row.CategoryName
    """

    run_query(query, {"rows": data})

    print("So Category:", len(data))


# =========================================================
# 7. IMPORT BRAND
# =========================================================

def import_brands(products):

    print("\n[2/9] IMPORT BRAND")

    data = (
        products[
            ["BrandID", "BrandName"]
        ]
        .drop_duplicates()
        .to_dict("records")
    )

    query = """
    UNWIND $rows AS row

    MERGE (b:Brand {
        brand_id: toInteger(row.BrandID)
    })

    SET b.name = row.BrandName
    """

    run_query(query, {"rows": data})

    print("So Brand:", len(data))


# =========================================================
# 8. IMPORT MATERIAL
# =========================================================

def import_materials(products):

    print("\n[3/9] IMPORT MATERIAL")

    data = (
        products[
            ["MaterialID", "MaterialName"]
        ]
        .drop_duplicates()
        .to_dict("records")
    )

    query = """
    UNWIND $rows AS row

    MERGE (m:Material {
        material_id: toInteger(row.MaterialID)
    })

    SET m.name = row.MaterialName
    """

    run_query(query, {"rows": data})

    print("So Material:", len(data))


# =========================================================
# 9. IMPORT GEMSTONE
# =========================================================

def import_gemstones(products):

    print("\n[4/9] IMPORT GEMSTONE")

    data = (
        products[
            ["GemstoneID", "GemstoneName"]
        ]
        .drop_duplicates()
        .to_dict("records")
    )

    query = """
    UNWIND $rows AS row

    MERGE (g:Gemstone {
        gemstone_id: toInteger(row.GemstoneID)
    })

    SET g.name = row.GemstoneName
    """

    run_query(query, {"rows": data})

    print("So Gemstone:", len(data))


# =========================================================
# 10. IMPORT COLLECTION
# =========================================================

def import_collections(products):

    print("\n[5/9] IMPORT COLLECTION")

    data = (
        products[
            ["CollectionID", "CollectionName"]
        ]
        .drop_duplicates()
        .to_dict("records")
    )

    query = """
    UNWIND $rows AS row

    MERGE (c:Collection {
        collection_id: toInteger(row.CollectionID)
    })

    SET c.name = row.CollectionName
    """

    run_query(query, {"rows": data})

    print("So Collection:", len(data))


# =========================================================
# 11. IMPORT PRODUCT
# =========================================================

def import_products(products):

    print("\n[6/9] IMPORT PRODUCT")

    data = products.to_dict("records")

    query = """
    UNWIND $rows AS row

    MERGE (p:Product {
        product_id: toInteger(row.ProductID)
    })

    SET
        p.sku = row.SKU,
        p.barcode = row.Barcode,
        p.name = row.ProductName,
        p.weight = toFloat(row.Weight),
        p.sale_price = toFloat(row.SalePrice),
        p.wholesale_price = toFloat(row.WholesalePrice),
        p.cost_price = toFloat(row.CostPrice),
        p.stock = toInteger(row.Stock)

    WITH p, row

    MATCH (category:Category {
        category_id: toInteger(row.CategoryID)
    })

    MATCH (brand:Brand {
        brand_id: toInteger(row.BrandID)
    })

    MATCH (material:Material {
        material_id: toInteger(row.MaterialID)
    })

    MATCH (gemstone:Gemstone {
        gemstone_id: toInteger(row.GemstoneID)
    })

    MATCH (collection:Collection {
        collection_id: toInteger(row.CollectionID)
    })

    MERGE (p)-[:BELONGS_TO]->(category)

    MERGE (p)-[:HAS_BRAND]->(brand)

    MERGE (p)-[:MADE_OF]->(material)

    MERGE (p)-[:HAS_GEMSTONE]->(gemstone)

    MERGE (p)-[:IN_COLLECTION]->(collection)
    """

    run_query(query, {"rows": data})

    print("So Product:", len(data))


# =========================================================
# 12. IMPORT CUSTOMER
# =========================================================

def import_customers(customers):

    print("\n[7/9] IMPORT CUSTOMER")

    data = customers.to_dict("records")

    query = """
    UNWIND $rows AS row

    MERGE (c:Customer {
        customer_id: row.CustomerID
    })

    SET
        c.full_name = row.FullName,
        c.gender = row.Gender,
        c.age = toInteger(row.Age),
        c.city = row.City,
        c.job = row.Job,
        c.income = toFloat(row.Income),
        c.favorite_category = row.FavoriteCategory,
        c.budget = toFloat(row.Budget),
        c.shopping_frequency = row.ShoppingFrequency,
        c.member_level = row.MemberLevel
    """

    run_query(query, {"rows": data})

    print("So Customer:", len(data))


# =========================================================
# 13. IMPORT ORDER
# =========================================================

def import_orders(orders):

    print("\n[8/9] IMPORT ORDER")

    data = orders.to_dict("records")

    query = """
    UNWIND $rows AS row

    MERGE (o:Order {
        order_id: row.OrderID
    })

    SET
        o.order_date = row.OrderDate,
        o.quantity = toInteger(row.Quantity),
        o.unit_price = toFloat(row.UnitPrice),
        o.total_amount = toFloat(row.TotalAmount),
        o.payment_method = row.PaymentMethod,
        o.status = row.Status,
        o.main_product_id = toInteger(row.ProductID)

    WITH o, row

    MATCH (c:Customer {
        customer_id: row.CustomerID
    })

    MERGE (c)-[:PLACED]->(o)
    """

    run_query(query, {"rows": data})

    print("So Order:", len(data))


# =========================================================
# 14. IMPORT ORDER DETAILS
# =========================================================

def import_order_details(order_details):

    print("\n[9/9] IMPORT ORDER DETAILS")

    data = order_details.to_dict("records")

    query = """
    UNWIND $rows AS row

    MATCH (o:Order {
        order_id: row.OrderID
    })

    MATCH (p:Product {
        product_id: toInteger(row.ProductID)
    })

    MERGE (o)-[r:CONTAINS]->(p)

    SET
        r.quantity = toInteger(row.Quantity),
        r.unit_price = toFloat(row.UnitPrice)
    """

    run_query(query, {"rows": data})

    print("So Order Details:", len(data))


# =========================================================
# 15. KIỂM TRA DỮ LIỆU TRƯỚC KHI IMPORT
# =========================================================

def check_files():

    files = [
        PRODUCT_FILE,
        CUSTOMER_FILE,
        ORDER_FILE,
        ORDER_DETAIL_FILE
    ]

    print("\n")
    print("=" * 70)
    print("KIEM TRA FILE")
    print("=" * 70)

    for file in files:

        print("\n", file)

        if not file.exists():

            raise FileNotFoundError(
                f"Khong tim thay file: {file}"
            )

        print("OK")


# =========================================================
# 16. MAIN
# =========================================================

def main():

    print("=" * 70)
    print("IMPORT JEWELRY KNOWLEDGE GRAPH")
    print("=" * 70)

    print("\nProject:")
    print(PROJECT_DIR)

    print("\nOutput:")
    print(OUTPUT_DIR)

    # -----------------------------------------------------
    # Kiểm tra file
    # -----------------------------------------------------

    check_files()

    # -----------------------------------------------------
    # Đọc CSV
    # -----------------------------------------------------

    print("\n")
    print("=" * 70)
    print("DOC DU LIEU CSV")
    print("=" * 70)

    products = pd.read_csv(PRODUCT_FILE)

    customers = pd.read_csv(CUSTOMER_FILE)

    orders = pd.read_csv(ORDER_FILE)

    order_details = pd.read_csv(
        ORDER_DETAIL_FILE
    )

    print("\nProducts:", len(products))

    print("Customers:", len(customers))

    print("Orders:", len(orders))

    print("Order details:", len(order_details))

    # -----------------------------------------------------
    # Kiểm tra kết nối
    # -----------------------------------------------------

    print("\n")
    print("=" * 70)
    print("KIEM TRA KET NOI NEO4J")
    print("=" * 70)

    driver.verify_connectivity()

    print("Ket noi Neo4j thanh cong.")

    # -----------------------------------------------------
    # Import
    # -----------------------------------------------------

    import_categories(products)

    import_brands(products)

    import_materials(products)

    import_gemstones(products)

    import_collections(products)

    import_products(products)

    import_customers(customers)

    import_orders(orders)

    import_order_details(order_details)

    # -----------------------------------------------------
    # Hoàn thành
    # -----------------------------------------------------

    print("\n")
    print("=" * 70)
    print("IMPORT THANH CONG")
    print("=" * 70)


# =========================================================
# CHẠY CHƯƠNG TRÌNH
# =========================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        print("\n")
        print("=" * 70)
        print("IMPORT THAT BAI")
        print("=" * 70)

        print("\nLoi:")
        print(e)

    finally:

        driver.close()