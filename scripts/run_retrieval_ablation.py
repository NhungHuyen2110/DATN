"""Cached real embedding + Qdrant memory + read-only test graph, five retrieval variants.

--smoke-only collects predictions on draft queries; never fabricates human labels
or relevance metrics. Price/stock source is explicitly a CSV SEED FIXTURE.
"""
import argparse
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODES = {'lexical': {'lexical'}, 'dense': {'dense'}, 'dense_lexical': {'dense', 'lexical'},
         'dense_graph': {'dense', 'graph'}, 'full_graph_reranked': {'dense', 'lexical', 'graph'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--model-revision', required=True)
    parser.add_argument('--queries', type=Path, required=True)
    parser.add_argument('--csv', type=Path, default=ROOT / 'output/products_ai.csv')
    parser.add_argument('--graph-uri')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--modes', nargs='+', choices=MODES, default=list(MODES))
    parser.add_argument('--smoke-only', action='store_true')
    parser.add_argument('--candidate-k', type=int, default=35)
    args = parser.parse_args()
    if (not args.model_path.is_dir() or args.model_path.name != args.model_revision
            or not re.fullmatch('[a-f0-9]{40}', args.model_revision)):
        parser.error('An existing cached snapshot matching the pinned revision is required')
    if args.output_dir.exists() or not args.output_dir.resolve().is_relative_to(ROOT):
        parser.error('A new output directory inside this workspace is required')
    if any('graph' in MODES[mode] for mode in args.modes) and args.graph_uri != 'bolt://127.0.0.1:17687':
        parser.error('Graph variants require the explicit isolated test graph on port17687')
    queries = [json.loads(line) for line in args.queries.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if not 1 <= len(queries) <= 1000 or len({item['query_id'] for item in queries}) != len(queries):
        parser.error('Unique query IDs and 1..1000 records required')
    if not args.smoke_only and any(item.get('reviewed') is not True or not item.get('reviewer') for item in queries):
        parser.error('Unreviewed labels require --smoke-only; quality metrics cannot be inferred')
    sha = hashlib.sha256(args.csv.read_bytes()).hexdigest()
    if any(item.get('dataset_sha256') != sha for item in queries):
        parser.error('Query dataset fingerprint differs from the CSV fixture')
    os.environ.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'EMBEDDING_REVISION': args.model_revision,
                       'HF_HOME': str(ROOT / '.local-tmp/models'), 'OMP_NUM_THREADS': '2'})
    sys.path[:0] = [str(ROOT), str(ROOT / 'AI')]
    from knowledge_graph.csv_validation import validate_csv
    from vector_index import index_products
    from jewelry_agents.search_service import search
    from jewelry_agents.reranking import GraphFeatureReranker
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer
    import torch
    torch.set_num_threads(2)
    validation = validate_csv(args.csv, ROOT / 'data')
    if validation['errors']:
        raise ValueError('Invalid source fixture')
    records = validation['records']
    catalog = {row['ProductID']: {'ProductID': row['ProductID'], 'ProductName': row['ProductName'], 'SKU': row['SKU'],
        'CategoryID': row['CategoryID'], 'Category': row['CategoryName'], 'MaterialID': row['MaterialID'],
        'Material': row['MaterialName'], 'GemstoneID': row['GemstoneID'], 'Gemstone': row['GemstoneName'],
        'Collection': row['CollectionName'], 'Price': row['SalePrice'], 'Stock': row['Stock']} for row in records}
    args.output_dir.mkdir(parents=True)
    init_start = time.perf_counter()
    encoder = SentenceTransformer(str(args.model_path), device='cpu', local_files_only=True)
    model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
    with ExitStack() as stack:
        stack.enter_context(patch('dotenv.load_dotenv', return_value=False))
        from jewelry_agents import retrieval
        vectors = stack.enter_context(closing(QdrantClient(location=':memory:')))
        index = index_products(vectors, encoder, records, model_name, args.model_revision, sha)
        stack.enter_context(patch.object(retrieval, 'get_dense_services', return_value=(vectors, encoder)))
        stack.enter_context(patch.object(retrieval, 'QDRANT_COLLECTION', index['collection']))
        stack.enter_context(patch.object(retrieval, 'EMBEDDING_MODEL', model_name))
        graph = None
        if args.graph_uri:
            from neo4j import GraphDatabase
            driver = stack.enter_context(GraphDatabase.driver(args.graph_uri,
                auth=('neo4j', os.environ['LUMIERE_GRAPH_PASSWORD']), connection_timeout=3, max_transaction_retry_time=5))
            with driver.session() as db:
                count = db.run('MATCH (p:Product) WHERE p.product_id IN $ids AND p.source_sha256=$sha RETURN count(p) AS count',
                               ids=list(catalog), sha=sha).single()['count']
                if count != len(catalog):
                    raise ValueError('Test graph is not aligned with the source fixture fingerprint')
            stack.enter_context(patch.object(retrieval, 'get_graph_driver', return_value=driver))
            graph = retrieval.graph_search_candidates
        initialization = time.perf_counter() - init_start
        summary = {'scope': 'CSV seed fixture; not live Business API', 'dataset_sha256': sha,
                   'model_revision': args.model_revision, 'index': index, 'graph_read_only': bool(graph),
                   'initialization_seconds': initialization, 'smoke_only': args.smoke_only,
                   'human_reviewed_queries': sum(item.get('reviewed') is True for item in queries),
                   'quality_metrics_computed': False, 'modes': {}}
        for mode in args.modes:
            samples = []
            with (args.output_dir / (mode + '.predictions.jsonl')).open('x', encoding='utf-8') as output:
                for item in queries:
                    start = time.perf_counter()
                    result = search(item['query'], item.get('top_k', 3), dense=retrieval.search_qdrant,
                                    catalog=lambda: catalog, parse_price=retrieval.extract_price_filter,
                                    graph=graph, sources=MODES[mode], candidate_k=args.candidate_k,
                                    reranker=GraphFeatureReranker() if mode == 'full_graph_reranked' else None,
                                    diagnostics=True)
                    elapsed = time.perf_counter() - start
                    products = result['products']
                    assert len(products) <= result.get('requested_k', 3)
                    record = {'query_id': item['query_id'], 'dataset_sha256': sha, 'mode': mode,
                              'status': result['status'], 'product_ids': [p['ProductID'] for p in products],
                              'latency_seconds': elapsed, 'requested_k': result.get('requested_k'),
                              'products': products, 'diagnostics': result.get('diagnostics'),
                              'label_reviewed': item.get('reviewed') is True}
                    output.write(json.dumps(record, ensure_ascii=False) + '\n')
                    samples.append(record)
            latencies = [item['latency_seconds'] for item in samples]
            summary['modes'][mode] = {'queries': len(samples), 'returned_products': sum(len(item['product_ids']) for item in samples),
                'degraded_queries': sum(item['status'] == 'degraded' for item in samples),
                'median_measured_seconds': statistics.median(latencies),
                'experimental_untuned_reranker': mode == 'full_graph_reranked'}
            print(json.dumps({'completed_mode': mode, **summary['modes'][mode]}), flush=True)
    with (args.output_dir / 'summary.json').open('x', encoding='utf-8') as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
