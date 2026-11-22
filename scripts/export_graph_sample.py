"""Read-only graph illustration data and Mermaid from the isolated seed graph."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uri', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.uri != 'bolt://127.0.0.1:17687' or args.output.exists() or args.output.with_suffix('.mmd').exists():
        parser.error('Explicit isolated graph and new outputs required')
    sys.path.insert(0, str(ROOT / 'AI'))
    from knowledge_graph.csv_validation import LOOKUPS
    from knowledge_graph.graph_writer import OWNER
    from neo4j import GraphDatabase
    with GraphDatabase.driver(args.uri, auth=('neo4j', os.environ['LUMIERE_GRAPH_PASSWORD']),
                              connection_timeout=3, max_transaction_retry_time=5) as driver:
        with driver.session(default_access_mode='READ') as db:
            records = [row.data() for row in db.run('''
                MATCH (p:Product)-[r]->(n)
                WHERE p.product_id IN $ids AND p.projection_owner=$owner AND type(r) IN $relations
                RETURN p.product_id AS product_id, p.name AS product_name, type(r) AS relationship,
                       labels(n)[0] AS label, properties(n) AS attributes
                ORDER BY product_id, relationship
            ''', ids=[1, 469], owner=OWNER, relations=[value[1] for value in LOOKUPS.values()])]
    if len(records) != 10:
        raise ValueError('Expected two products with five verified taxonomy edges each')
    report = {'scope': 'actual isolated Neo4j, CSV seed projection, not live business facts',
              'read_only': True, 'products': [1, 469], 'edges': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    lines, nodes = ['flowchart LR'], set()
    for edge in records:
        pid = 'p' + str(edge['product_id'])
        key = edge['label'].lower() + '_id'
        target = edge['label'] + str(edge['attributes'][key])
        for identity, title in ((pid, f"Product {edge['product_id']}: {edge['product_name']}"),
                                (target, f"{edge['label']} {edge['attributes'][key]}: {edge['attributes']['name']}")):
            if identity not in nodes:
                lines.append(f'  {identity}[{json.dumps(title, ensure_ascii=False)}]')
                nodes.add(identity)
        lines.append(f"  {pid} -->|{edge['relationship']}| {target}")
    with args.output.with_suffix('.mmd').open('x', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print(json.dumps({'nodes': len(nodes), 'relationships': len(records), 'read_only': True}))


if __name__ == '__main__':
    main()
