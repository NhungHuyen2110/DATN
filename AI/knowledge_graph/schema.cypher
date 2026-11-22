// Controlled legacy-compatible projection. Neo4j 5+ syntax.
// Execute only against an identified, backed-up development database.
// Existing duplicates must be reconciled before enabling these constraints.
CREATE CONSTRAINT lumiere_product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.product_id IS UNIQUE;
CREATE CONSTRAINT lumiere_category_id IF NOT EXISTS
FOR (c:Category) REQUIRE c.category_id IS UNIQUE;
CREATE CONSTRAINT lumiere_brand_id IF NOT EXISTS
FOR (b:Brand) REQUIRE b.brand_id IS UNIQUE;
CREATE CONSTRAINT lumiere_material_id IF NOT EXISTS
FOR (m:Material) REQUIRE m.material_id IS UNIQUE;
CREATE CONSTRAINT lumiere_gemstone_id IF NOT EXISTS
FOR (g:Gemstone) REQUIRE g.gemstone_id IS UNIQUE;
CREATE CONSTRAINT lumiere_collection_id IF NOT EXISTS
FOR (c:Collection) REQUIRE c.collection_id IS UNIQUE;
