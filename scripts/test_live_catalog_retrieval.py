"""Real cached embeddings/Neo4j/Qdrant memory with authoritative HTTP catalog on a NEW PostgreSQL fixture."""
import argparse
from contextlib import ExitStack, closing
from decimal import Decimal
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    from sqlalchemy import create_engine, inspect, update
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    url = make_url(os.environ['LUMIERE_SYNC_TEST_URL'])
    if url.host != '127.0.0.1' or url.port != 15439 or not url.database.startswith('lumiere_test_catalog_'):
        parser.error('Dedicated loopback test PostgreSQL required')
    if os.environ.get('LUMIERE_SYNC_TEST_GRAPH_URI') != 'bolt://127.0.0.1:17687':
        parser.error('Dedicated test graph URI required')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 18001))
    env = {**os.environ, 'LUMIERE_LOAD_DOTENV': 'false', 'POSTGRES_DB': url.database,
           'POSTGRES_USER': url.username, 'POSTGRES_PASSWORD': url.password, 'POSTGRES_HOST': '127.0.0.1',
           'POSTGRES_PORT': '15439', 'PRODUCT_INDEX_SYNC_ENABLED': 'false', 'LUMIERE_METRICS_ENABLED': 'false',
           'BUSINESS_API_URL': 'http://127.0.0.1:18001', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
           'HF_HOME': str(ROOT / '.local-tmp/models'), 'EMBEDDING_REVISION': REVISION}
    os.environ.update(env)
    sys.path[:0] = [str(ROOT), str(ROOT / 'backend'), str(ROOT / 'AI')]
    from app.main import app
    from app.models import Product, Category, Brand, Material, Gemstone, Collection
    from knowledge_graph.csv_validation import validate_csv
    from jewelry_agents.business_catalog import fetch_catalog
    from jewelry_agents.search_service import search
    from vector_index import index_products
    from qdrant_client import QdrantClient
    from neo4j import GraphDatabase
    engine = create_engine(url, connect_args={'connect_timeout': 3})
    server = None
    artifacts = ROOT / '.local-tmp' / url.database
    artifacts.mkdir(exist_ok=False)
    try:
        if inspect(engine).get_table_names():
            raise ValueError('Target DB must be empty')
        from alembic import command
        from alembic.config import Config
        config = Config(str(ROOT / 'backend/alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'backend/alembic'))
        command.upgrade(config, 'head')
        validated = validate_csv(ROOT / 'output/products_ai.csv', ROOT / 'data')
        if validated['errors']:
            raise ValueError('Invalid seed fixture')
        records = validated['records']
        with Session(engine) as db, db.begin():
            for prefix, model in (('Category', Category), ('Brand', Brand), ('Material', Material),
                                  ('Gemstone', Gemstone), ('Collection', Collection)):
                items = {row[prefix + 'ID']: row[prefix + 'Name'] for row in records}
                db.add_all([model(id=pid, name=name) for pid, name in items.items()])
            db.flush()
            db.add_all([Product(id=row['ProductID'], sku=row['SKU'], barcode=row['Barcode'], name=row['ProductName'],
                category_id=row['CategoryID'], brand_id=row['BrandID'], material_id=row['MaterialID'],
                gemstone_id=row['GemstoneID'], collection_id=row['CollectionID'], weight=Decimal(row['Weight']),
                sale_price=Decimal(row['SalePrice']), wholesale_price=Decimal(row['WholesalePrice']),
                cost_price=Decimal(row['CostPrice']), stock=row['Stock']) for row in records])
        with (artifacts / 'server.log').open('w', encoding='utf-8') as log:
            server = subprocess.Popen([sys.executable, '-B', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
                                       '--port', '18001', '--no-access-log'], cwd=ROOT / 'backend', env=env,
                                      stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        ready = False
        for _ in range(30):
            try:
                with urlopen('http://127.0.0.1:18001/health/ready', timeout=2) as response:
                    ready = response.status == 200
                if ready:
                    break
            except OSError:
                time.sleep(1)
        if not ready:
            raise RuntimeError('Fixture source API unavailable')
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(2)
        model_path = ROOT / '.local-tmp/models/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots' / REVISION
        model = SentenceTransformer(str(model_path), device='cpu', local_files_only=True)
        with ExitStack() as stack:
            stack.enter_context(patch('dotenv.load_dotenv', return_value=False))
            from jewelry_agents import retrieval
            vectors = stack.enter_context(closing(QdrantClient(location=':memory:')))
            index = index_products(vectors, model, records, 'paraphrase-multilingual-MiniLM-L12-v2', REVISION, 'postgres-seed-fixture')
            stack.enter_context(patch.object(retrieval, 'get_dense_services', return_value=(vectors, model)))
            stack.enter_context(patch.object(retrieval, 'QDRANT_COLLECTION', index['collection']))
            driver = stack.enter_context(GraphDatabase.driver('bolt://127.0.0.1:17687',
                auth=('neo4j', os.environ['LUMIERE_SYNC_TEST_GRAPH_PASSWORD']), connection_timeout=3, max_transaction_retry_time=5))
            stack.enter_context(patch.object(retrieval, 'get_graph_driver', return_value=driver))
            samples = []
            for query in ('Top 3 nhẫn dưới 8 triệu', 'Top 3 nhẫn cùng loại đá với sản phẩm 1'):
                result = search(query, 3, dense=retrieval.search_qdrant, catalog=fetch_catalog,
                                parse_price=retrieval.extract_price_filter, graph=retrieval.graph_search_candidates)
                assert result['returned_k'] == 3
                assert all(item['verified_source'] == 'business_api' for item in result['products'])
                if 'cùng loại đá' in query:
                    reference = fetch_catalog()[1]
                    assert all(item['GemstoneID'] == reference['GemstoneID'] for item in result['products'])
                    assert any(item['graph_paths'] for item in result['products'])
                samples.append({'query': query, 'status': result['status'], 'products': result['products']})
            changed = samples[0]['products'][0]['ProductID']
            mutated = False
            def dense_with_concurrent_update(*args, **kwargs):
                nonlocal mutated
                found = retrieval.search_qdrant(*args, **kwargs)
                if not mutated:
                    with Session(engine) as db, db.begin():
                        db.execute(update(Product).where(Product.id == changed).values(sale_price=1000000000, stock=0))
                    mutated = True
                return found
            final = search('Top 3 nhẫn dưới 8 triệu', 3, dense=dense_with_concurrent_update, catalog=fetch_catalog,
                           parse_price=retrieval.extract_price_filter, graph=retrieval.graph_search_candidates)
            assert final['returned_k'] == 3 and changed not in [item['ProductID'] for item in final['products']]
            current = fetch_catalog()
            assert all(Decimal(str(item['Price'])) == Decimal(str(current[item['ProductID']]['Price']))
                       and item['Stock'] == current[item['ProductID']]['Stock'] for item in final['products'])
        report = {'successful': True, 'catalog': 'actual HTTP Business API backed by PostgreSQL with 500 CSV seed fixtures',
                  'model': 'actual cached MiniLM on D', 'model_revision': REVISION, 'qdrant': 'actual memory engine',
                  'neo4j': 'actual isolated read-only seed graph', 'samples': samples,
                  'concurrent_price_stock_change': {'changed_product_id': changed, 'stale_candidate_excluded': True,
                                                     'final_products': final['products']},
                  'production_accessed': False, 'quality_benchmark': False}
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(json.dumps({'successful': True, 'live_fixture_products': len(current), 'changed_candidate_excluded': changed}))
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            server.wait(timeout=10)
        engine.dispose()


if __name__ == '__main__':
    main()
