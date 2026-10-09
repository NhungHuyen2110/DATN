
from neo4j import GraphDatabase

class GraphRecommender:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(
            uri, auth=(username, password)
        )

    def recommend(self, product_id, limit=20):
        query = """
        MATCH (source:Product {product_id: $product_id})
        MATCH (candidate:Product)
        WHERE candidate.product_id <> source.product_id
          AND coalesce(candidate.stock, 0) > 0

        OPTIONAL MATCH
          (source)-[:BELONGS_TO]->(c:Category)
          <-[:BELONGS_TO]-(candidate)
        WITH source, candidate, count(DISTINCT c) AS category_match

        OPTIONAL MATCH
          (source)-[:MADE_OF]->(m:Material)
          <-[:MADE_OF]-(candidate)
        WITH source, candidate, category_match,
             count(DISTINCT m) AS material_match

        OPTIONAL MATCH
          (source)-[:HAS_GEMSTONE]->(g:Gemstone)
          <-[:HAS_GEMSTONE]-(candidate)
        WITH candidate, category_match, material_match,
             count(DISTINCT g) AS gemstone_match

        WITH candidate,
             category_match * 0.4 +
             material_match * 0.3 +
             gemstone_match * 0.3 AS graph_score

        WHERE graph_score > 0

        RETURN
          candidate.product_id AS ProductID,
          graph_score AS GraphScore
        ORDER BY GraphScore DESC, ProductID
        LIMIT $limit
        """

        with self.driver.session() as session:
            result = session.run(
                query,
                product_id=int(product_id),
                limit=int(limit)
            )
            return [record.data() for record in result]

    def close(self):
        self.driver.close()
