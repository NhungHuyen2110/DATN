"""Pure projection contracts and drift comparison; no clients, models or writes."""
from collections import Counter
from decimal import Decimal
import hashlib
from shared.verified_attributes import CATALOG_OWNER

VECTOR_FIELDS = {
    'ProductID': 'ProductID', 'ProductName': 'ProductName', 'SKU': 'SKU',
    'Category': 'CategoryName', 'CategoryID': 'CategoryID', 'Material': 'MaterialName',
    'Gemstone': 'GemstoneName', 'GemstoneID': 'GemstoneID', 'Collection': 'CollectionName',
}
TEXT_FIELDS = ('ProductName', 'CategoryName', 'BrandName', 'MaterialName', 'GemstoneName', 'CollectionName')
TAXONOMY = {'Category': 'BELONGS_TO', 'Brand': 'HAS_BRAND', 'Material': 'MADE_OF',
            'Gemstone': 'HAS_GEMSTONE', 'Collection': 'IN_COLLECTION'}


def embedding_document(row, payload):
    text = '. '.join(str(row[field]) for field in TEXT_FIELDS)
    facts = payload.get('verified_attributes') or []
    return text + ('. ' + '. '.join(fact['name'] for fact in facts) if facts else '')


def document_sha256(row, payload):
    return hashlib.sha256(embedding_document(row, payload).encode('utf-8')).hexdigest()


def compare_indexes(products, graph_nodes, graph_edges, vector_points, fingerprint):
    """Compare a captured read-only snapshot. Tombstones are not active products.

    A SQL product is index eligible even at stock zero. The current schema has
    no active/hidden/description fields; missing SQL products are tombstones.
    Unknown ownership/schema is a blocker, never an automatic deletion plan.
    """
    source = {p['ProductID']: p for p in products}
    issues = []

    def issue(store, pid, field, actual=None, expected=None):
        issues.append({'store': store, 'product_id': pid, 'field': field,
                       'actual': actual, 'expected': expected})

    def duplicates(store, records, key):
        for value, count in Counter(key(p) for p in records).items():
            if count > 1:
                issue(store, value, 'duplicate_identity', count, 1)

    duplicates('business', products, lambda p: p['ProductID'])
    duplicates('business_sku', products, lambda p: p['SKU'])
    nodes = [n.get('properties', n) for n in graph_nodes]
    duplicates('graph', nodes, lambda p: p.get('product_id'))
    duplicates('vector', vector_points, lambda p: p['id'])
    active = {p.get('product_id'): p for p in nodes if not p.get('is_deleted', False)}
    duplicates('graph_sku', list(active.values()), lambda p: p.get('sku'))
    duplicates('vector_payload_sku', vector_points, lambda p: (p.get('payload') or {}).get('SKU'))
    vectors = {p['id']: p for p in vector_points}
    for store, rows in [('graph', active), ('vector', vectors)]:
        for pid in sorted(set(source) - set(rows)):
            issue(store, pid, 'missing')
        for pid in sorted(set(rows) - set(source)):
            issue(store, pid, 'extra_active')
    by_edge = {}
    for edge in graph_edges:
        by_edge.setdefault((edge['product_id'], edge['type']), []).append(edge)
    for pid, row in source.items():
        node = active.get(pid)
        if node is not None:
            expected = {'name': row['ProductName'], 'sku': row['SKU'], 'barcode': row['Barcode'],
                        'stock': row['Stock'], 'is_deleted': False, 'projection_owner': CATALOG_OWNER,
                        'sale_price_minor': int(Decimal(str(row['SalePrice'])) * 100)}
            for field, value in expected.items():
                if node.get(field) != value:
                    issue('graph', pid, field, node.get(field), value)
            for field, value in [('sale_price_decimal', row['SalePrice']), ('sale_price', row['SalePrice']),
                                 ('weight', row['Weight'])]:
                try:
                    matches = Decimal(str(node.get(field))) == Decimal(str(value))
                except Exception:
                    matches = False
                if not matches:
                    issue('graph', pid, field, node.get(field), value)
            for label, relation in TAXONOMY.items():
                edges = by_edge.get((pid, relation), [])
                correct = [e for e in edges if e['target'].get(label.lower() + '_id') == row[label + 'ID']
                           and e['target'].get('name') == row[label + 'Name'] and label in e['labels']]
                correct = [e for e in correct if e.get('properties', {}).get('projection_owner') == CATALOG_OWNER]
                if len(edges) != 1 or len(correct) != 1:
                    issue('graph', pid, relation, len(correct), 'one exact endpoint/name')
        point = vectors.get(pid)
        if point is not None:
            payload = point.get('payload') or {}
            for field, source_field in VECTOR_FIELDS.items():
                if payload.get(field) != row[source_field]:
                    issue('vector', pid, field, payload.get(field), row[source_field])
            if payload.get('embedding_fingerprint') != fingerprint:
                issue('vector', pid, 'embedding_fingerprint', payload.get('embedding_fingerprint'), fingerprint)
            identity = hashlib.sha256(f"{payload.get('embedding_model')}:{payload.get('embedding_revision')}:384:cosine".encode()).hexdigest()
            if identity != fingerprint:
                issue('vector', pid, 'embedding_identity', identity, fingerprint)
            if point.get('vector_dimension') != 384 or not point.get('finite_nonzero', False):
                issue('vector', pid, 'vector_contract', point.get('vector_dimension'), '384 finite/nonzero')
    return {'eligible_products': len(source), 'active_graph_products': len(active),
            'vector_products': len(vectors), 'issues': issues,
            'affected_product_ids': sorted({i['product_id'] for i in issues if isinstance(i['product_id'], int)}),
            'pass': not issues}
