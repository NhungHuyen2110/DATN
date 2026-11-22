"""Owned evidence overlay. Only the authenticated review store supplies these rows."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.verified_attributes import ATTRIBUTE_RELATIONSHIPS, REVIEW_OWNER


def write_reviewed_attributes(tx, rows, catalog_owner, conflict_type):
    selected = [row for row in rows if row.get('_reviewed_facts_present')]
    if not selected:
        return
    ids = [row['ProductID'] for row in selected]
    for label, relationship in ATTRIBUTE_RELATIONSHIPS.items():
        # Identifiers are source-controlled; all data are parameters.
        conflicts = tx.run(f'''
            MATCH (p:Product)-[r:{relationship}]->()
            WHERE p.product_id IN $ids AND coalesce(r.projection_owner,'') <> $owner
            RETURN count(r) AS count
        ''', ids=ids, owner=REVIEW_OWNER).single()['count']
        if conflicts:
            raise conflict_type('Unmanaged reviewed relationships cannot be overwritten')
        tx.run(f'''
            MATCH (p:Product)-[r:{relationship}]->()
            WHERE p.product_id IN $ids AND r.projection_owner=$owner
            SET r.active=false
        ''', ids=ids, owner=REVIEW_OWNER).consume()
        facts = [{**fact, 'product_id': row['ProductID']} for row in selected
                 for fact in row['_reviewed_facts'] if fact['label'] == label]
        if not facts:
            continue
        result = tx.run(f'''
            UNWIND $facts AS fact
            MATCH (p:Product {{product_id:fact.product_id, projection_owner:$catalog_owner}})
            MERGE (entity:{label} {{canonical_id:fact.canonical_id}})
            ON CREATE SET entity.projection_owner=$owner
            WITH p,entity,fact WHERE entity.projection_owner=$owner
            SET entity.name=fact.name
            MERGE (p)-[edge:{relationship}]->(entity)
            SET edge.projection_owner=$owner, edge.active=true,
                edge.source_reference_sha256=fact.source_reference_sha256,
                edge.review_id=fact.review_id, edge.review_version=fact.review_version,
                edge.reviewed_at=fact.reviewed_at, edge.extraction_method='human_review'
            RETURN count(edge) AS count
        ''', facts=facts, owner=REVIEW_OWNER, catalog_owner=catalog_owner).single()['count']
        if result != len(facts):
            raise conflict_type('Reviewed entity ownership or product identity differs')


def verify_reviewed_attributes(session, rows):
    selected = [row for row in rows if row.get('_reviewed_facts_present')]
    expected = {(row['ProductID'], fact['label'], fact['canonical_id'], fact['source_reference_sha256'],
                 fact['review_id'], fact['review_version'], REVIEW_OWNER, REVIEW_OWNER)
                for row in selected for fact in row['_reviewed_facts']}
    actual = []
    ids = [row['ProductID'] for row in selected]
    for label, relationship in ATTRIBUTE_RELATIONSHIPS.items():
        for record in session.run(f'''
            MATCH (p:Product)-[r:{relationship}]->(entity)
            WHERE p.product_id IN $ids AND r.active=true
            RETURN p.product_id AS product_id, labels(entity) AS labels,
                   entity.canonical_id AS canonical_id,
                   r.source_reference_sha256 AS evidence, r.review_id AS review_id,
                   r.review_version AS version, r.projection_owner AS edge_owner,
                   entity.projection_owner AS node_owner
        ''', ids=ids):
            actual.append((record['product_id'], label if record['labels'] == [label] else 'invalid_label',
                           record['canonical_id'], record['evidence'], record['review_id'], record['version'],
                           record['edge_owner'], record['node_owner']))
    unique = set(actual)
    return {'expected': len(expected), 'active': len(actual),
            'violations': len(expected - unique) + len(unique - expected) + len(actual) - len(unique)}
