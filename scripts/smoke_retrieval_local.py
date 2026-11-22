"""Real cached embedding + Qdrant memory + optional read-only test graph.

Catalog is an explicit CSV FIXTURE, not a claim of live PostgreSQL verification.
No .env, model download, remote Qdrant writes or business database writes.
"""
import argparse
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--model-revision', required=True)
    parser.add_argument('--csv', type=Path, default=ROOT / 'output/products_ai.csv')
    parser.add_argument('--graph-uri')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--query', action='append', help='Explicit extra/replacement smoke query; repeatable')
    args = parser.parse_args()
    if not args.model_path.is_dir() or args.report.exists():
        parser.error('Model directory missing or report already exists')
    if args.graph_uri and urlsplit(args.graph_uri).hostname not in {'127.0.0.1', 'localhost', '::1'}:
        parser.error('Graph must be explicit loopback test URI')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['EMBEDDING_REVISION'] = args.model_revision
    sys.path.insert(0, str(ROOT / 'AI'))
    sys.path.insert(0, str(ROOT))
    from knowledge_graph.csv_validation import validate_csv
    from vector_index import index_products
    from jewelry_agents.search_service import search
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer
    import torch
    torch.set_num_threads(2)
    result = validate_csv(args.csv, ROOT / 'data')
    if result['errors']:
        raise ValueError('Invalid fixture CSV')
    records = result['records']
    model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
    started = time.perf_counter()
    model = SentenceTransformer(str(args.model_path), device='cpu', local_files_only=True)
    catalog = {row['ProductID']: {
        'ProductID': row['ProductID'], 'ProductName': row['ProductName'], 'SKU': row['SKU'],
        'CategoryID': row['CategoryID'], 'Category': row['CategoryName'], 'MaterialID': row['MaterialID'],
        'Material': row['MaterialName'], 'GemstoneID': row['GemstoneID'], 'Gemstone': row['GemstoneName'],
        'Collection': row['CollectionName'], 'Price': row['SalePrice'], 'Stock': row['Stock']}
        for row in records}
    with ExitStack() as stack:
        stack.enter_context(patch('dotenv.load_dotenv', return_value=False))
        from jewelry_agents import retrieval
        client = stack.enter_context(closing(QdrantClient(location=':memory:')))
        index = index_products(client, model, records, model_name, args.model_revision,
                               hashlib.sha256(args.csv.read_bytes()).hexdigest())
        retrieval.get_dense_services = lambda: (client, model)
        retrieval.QDRANT_COLLECTION = index['collection']
        retrieval.EMBEDDING_MODEL = model_name
        graph = None
        if args.graph_uri:
            from neo4j import GraphDatabase
            driver = stack.enter_context(GraphDatabase.driver(
                args.graph_uri, auth=('neo4j', os.environ['LUMIERE_GRAPH_PASSWORD']), connection_timeout=5))
            retrieval.get_graph_driver = lambda: driver
            graph = retrieval.graph_search_candidates
        samples = []
        for query in (args.query or ['Top 3 nhẫn dưới 8 triệu', 'Top 1 bông tai moissanite']):
            output = search(query, 3, dense=retrieval.search_qdrant, catalog=lambda: catalog,
                            parse_price=retrieval.extract_price_filter, graph=graph)
            samples.append({'query': query, 'status': output['status'], 'requested_k': output.get('requested_k'),
                            'returned_k': len(output['products']), 'products': output['products'],
                            'understanding': output['understanding']})
        report = {'scope': 'CSV seed fixture, not live Business API; not a relevance benchmark',
                  'model': model_name, 'revision': args.model_revision, 'index': index,
                  'graph_read_only': bool(graph), 'elapsed_seconds': round(time.perf_counter() - started, 3),
                  'samples': samples}
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({'indexed_products': index['verified_products'], 'dimension': index['dimension'],
                      'samples': len(samples), 'elapsed_seconds': report['elapsed_seconds']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
