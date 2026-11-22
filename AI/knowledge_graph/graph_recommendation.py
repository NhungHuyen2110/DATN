
from neo4j import GraphDatabase

class GraphRecommender:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(
            uri, auth=(username, password), connection_timeout=3, max_transaction_retry_time=5
        )

    def recommend(self, product_id, limit=20):
        query = """
        MATCH (source:Product {product_id: $product_id})
        MATCH (source)-[left]->(attribute)<-[right]-(candidate:Product)
        WHERE candidate.product_id <> source.product_id
          AND coalesce(candidate.stock, 0) > 0
          AND type(left) = type(right)
          AND type(left) IN ['BELONGS_TO', 'MADE_OF', 'HAS_GEMSTONE']
          AND ((type(left) = 'BELONGS_TO' AND attribute:Category)
            OR (type(left) = 'MADE_OF' AND attribute:Material)
            OR (type(left) = 'HAS_GEMSTONE' AND attribute:Gemstone))
        WITH source, candidate,
             collect(DISTINCT type(left)) AS matched_types,
             collect(DISTINCT {source_product_id: source.product_id,
                relationship: type(left),
                attribute_id: coalesce(attribute.category_id, attribute.material_id, attribute.gemstone_id),
                attribute_name: attribute.name, candidate_product_id: candidate.product_id}) AS paths
        WITH candidate, paths,
             CASE WHEN 'BELONGS_TO' IN matched_types THEN 0.4 ELSE 0 END +
             CASE WHEN 'MADE_OF' IN matched_types THEN 0.3 ELSE 0 END +
             CASE WHEN 'HAS_GEMSTONE' IN matched_types THEN 0.3 ELSE 0 END AS graph_score
        WHERE graph_score > 0
        RETURN
          candidate.product_id AS ProductID,
          graph_score AS GraphScore, paths
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
