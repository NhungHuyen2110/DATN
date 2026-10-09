from pathlib import Path
from neo4j import GraphDatabase


# =========================================================
# 1. CẤU HÌNH NEO4J
# =========================================================

URI = "neo4j://127.0.0.1:7687"

USERNAME = "neo4j"

PASSWORD = "12345678"


# =========================================================
# 2. KẾT NỐI
# =========================================================

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)


# =========================================================
# 3. LẤY THÔNG TIN PRODUCT
# =========================================================

def get_product(product_id):

    query = """
    MATCH (p:Product {
        product_id: $product_id
    })

    OPTIONAL MATCH (p)-[:BELONGS_TO]->(category:Category)

    OPTIONAL MATCH (p)-[:HAS_BRAND]->(brand:Brand)

    OPTIONAL MATCH (p)-[:MADE_OF]->(material:Material)

    OPTIONAL MATCH (p)-[:HAS_GEMSTONE]->(gemstone:Gemstone)

    OPTIONAL MATCH (p)-[:IN_COLLECTION]->(collection:Collection)

    RETURN
        p.product_id AS product_id,
        p.name AS product_name,
        p.sku AS sku,
        p.sale_price AS sale_price,
        p.wholesale_price AS wholesale_price,
        p.cost_price AS cost_price,
        p.stock AS stock,
        p.weight AS weight,

        category.name AS category,

        brand.name AS brand,

        material.name AS material,

        gemstone.name AS gemstone,

        collection.name AS collection
    """

    with driver.session() as session:

        result = session.run(
            query,
            product_id=int(product_id)
        )

        record = result.single()

        if record is None:
            return None

        return record.data()


# =========================================================
# 4. LẤY NHIỀU PRODUCT
# =========================================================

def get_products(product_ids):

    query = """
    MATCH (p:Product)

    WHERE p.product_id IN $product_ids

    OPTIONAL MATCH (p)-[:BELONGS_TO]->(category:Category)

    OPTIONAL MATCH (p)-[:HAS_BRAND]->(brand:Brand)

    OPTIONAL MATCH (p)-[:MADE_OF]->(material:Material)

    OPTIONAL MATCH (p)-[:HAS_GEMSTONE]->(gemstone:Gemstone)

    OPTIONAL MATCH (p)-[:IN_COLLECTION]->(collection:Collection)

    RETURN
        p.product_id AS product_id,
        p.name AS product_name,
        p.sku AS sku,
        p.sale_price AS sale_price,
        p.stock AS stock,
        p.weight AS weight,

        category.name AS category,

        brand.name AS brand,

        material.name AS material,

        gemstone.name AS gemstone,

        collection.name AS collection

    ORDER BY p.product_id
    """

    with driver.session() as session:

        result = session.run(
            query,
            product_ids=[
                int(x)
                for x in product_ids
            ]
        )

        return [
            record.data()
            for record in result
        ]


# =========================================================
# 5. TÌM SẢN PHẨM THEO THUỘC TÍNH
# =========================================================

def search_products_by_attributes(
    category=None,
    brand=None,
    material=None,
    gemstone=None,
    collection=None
):

    query = """
    MATCH (p:Product)

    OPTIONAL MATCH (p)-[:BELONGS_TO]->(categoryNode:Category)

    OPTIONAL MATCH (p)-[:HAS_BRAND]->(brandNode:Brand)

    OPTIONAL MATCH (p)-[:MADE_OF]->(materialNode:Material)

    OPTIONAL MATCH (p)-[:HAS_GEMSTONE]->(gemstoneNode:Gemstone)

    OPTIONAL MATCH (p)-[:IN_COLLECTION]->(collectionNode:Collection)

    WHERE
        ($category IS NULL OR categoryNode.name = $category)
        AND
        ($brand IS NULL OR brandNode.name = $brand)
        AND
        ($material IS NULL OR materialNode.name = $material)
        AND
        ($gemstone IS NULL OR gemstoneNode.name = $gemstone)
        AND
        ($collection IS NULL OR collectionNode.name = $collection)

    RETURN
        p.product_id AS product_id,
        p.name AS product_name,
        p.sale_price AS sale_price,
        p.stock AS stock,

        categoryNode.name AS category,
        brandNode.name AS brand,
        materialNode.name AS material,
        gemstoneNode.name AS gemstone,
        collectionNode.name AS collection

    ORDER BY p.sale_price ASC
    """

    with driver.session() as session:

        result = session.run(
            query,
            category=category,
            brand=brand,
            material=material,
            gemstone=gemstone,
            collection=collection
        )

        return [
            record.data()
            for record in result
        ]


# =========================================================
# 6. LỊCH SỬ MUA HÀNG CỦA KHÁCH HÀNG
# =========================================================

def get_customer_history(customer_id):

    query = """
    MATCH (c:Customer {
        customer_id: $customer_id
    })

    OPTIONAL MATCH
        (c)-[:PLACED]->(o:Order)-[r:CONTAINS]->(p:Product)

    RETURN
        c.customer_id AS customer_id,
        c.full_name AS customer_name,

        o.order_id AS order_id,
        o.order_date AS order_date,
        o.status AS order_status,

        p.product_id AS product_id,
        p.name AS product_name,

        r.quantity AS quantity,
        r.unit_price AS unit_price

    ORDER BY o.order_date DESC
    """

    with driver.session() as session:

        result = session.run(
            query,
            customer_id=customer_id
        )

        return [
            record.data()
            for record in result
        ]


# =========================================================
# 7. TÌM SẢN PHẨM ĐÃ MUA BỞI KHÁCH HÀNG
# =========================================================

def get_customer_purchased_products(customer_id):

    query = """
    MATCH
        (c:Customer {
            customer_id: $customer_id
        })
        -[:PLACED]->(o:Order)
        -[:CONTAINS]->(p:Product)

    RETURN DISTINCT
        p.product_id AS product_id,
        p.name AS product_name
    """

    with driver.session() as session:

        result = session.run(
            query,
            customer_id=customer_id
        )

        return [
            record.data()
            for record in result
        ]


# =========================================================
# 8. ĐÓNG CONNECTION
# =========================================================

def close():

    driver.close()