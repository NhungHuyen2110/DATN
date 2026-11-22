"""Explicit isolated PostgreSQL + real Neo4j + Qdrant memory lifecycle, synthetic embeddings."""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', required=True, action='store_true')
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Evidence already exists')
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from neo4j import GraphDatabase
    from qdrant_client import QdrantClient
    url = make_url(os.environ['LUMIERE_SYNC_TEST_URL'])
    uri = os.environ.get('LUMIERE_SYNC_TEST_GRAPH_URI')
    if (url.drivername != 'postgresql+psycopg' or url.host != '127.0.0.1' or url.port != 15439
            or not url.database or not url.database.startswith('lumiere_test_projection_')
            or url.database.rsplit('_', 1)[-1] not in {str(i) for i in range(1, 10)}
            or uri != 'bolt://127.0.0.1:17687'):
        parser.error('Only explicit dedicated local integration targets allowed')
    os.environ.update({'LUMIERE_LOAD_DOTENV': 'false', 'POSTGRES_DB': 'unused', 'POSTGRES_PASSWORD': 'unused',
                       'PRODUCT_INDEX_SYNC_ENABLED': 'true'})
    sys.path[:0] = [str(ROOT), str(ROOT / 'backend'), str(ROOT / 'AI')]
    from app.core.database import Base
    from app.models import Product, Category, Material, Gemstone, Brand, Collection
    from app.services.product_index_worker import run_one
    from product_projection import ProductProjection
    from vector_index import index_identity
    attempt = int(url.database.rsplit('_', 1)[-1])
    pid, taxonomy = 900020 + attempt, 990020 + attempt
    server_url = os.getenv('LUMIERE_SYNC_TEST_QDRANT_URL')
    actual_encoder = None
    model_name, revision = 'synthetic-integration', 'revision-1'
    if server_url:
        if server_url != 'http://127.0.0.1:16334':
            parser.error('Only the dedicated Qdrant test container on port16334 is allowed')
        revision = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
        model_path = ROOT / '.local-tmp/models/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots' / revision
        if not model_path.is_dir():
            parser.error('Expected the existing pinned model cache on D')
        print(json.dumps({'stage': 'loading_pinned_model_on_d'}), flush=True)
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(2)
        actual_encoder = SentenceTransformer(str(model_path), device='cpu', local_files_only=True)
        print(json.dumps({'stage': 'model_loaded'}), flush=True)
        model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
    class Encoder:
        fail_once = True
        def get_sentence_embedding_dimension(self):
            return actual_encoder.get_sentence_embedding_dimension() if actual_encoder is not None else 3
        def encode(self, texts):
            if self.fail_once:
                self.fail_once = False
                raise TimeoutError('synthetic interrupted embedding after graph commit')
            return actual_encoder.encode(texts) if actual_encoder is not None else [[1., 0., 0.] for _ in texts]
    # Loopback-only fixture server: avoid Windows SSPI/GSS/TLS negotiation while
    # testing ML-library coexistence. Production connection settings are untouched.
    engine = create_engine(url, connect_args={'connect_timeout': 10, 'sslmode': 'disable', 'gssencmode': 'disable'})
    try:
        print(json.dumps({'stage': 'checking_empty_postgres_target'}), flush=True)
        if inspect(engine).get_table_names():
            raise ValueError('Test DB must be empty')
        with GraphDatabase.driver(uri, auth=('neo4j', os.environ['LUMIERE_SYNC_TEST_GRAPH_PASSWORD']),
                                  connection_timeout=3, max_transaction_retry_time=5) as driver, \
                closing(QdrantClient(url=server_url, timeout=10) if server_url else QdrantClient(location=':memory:')) as vectors:
            print(json.dumps({'stage': 'checking_reserved_graph_fixture'}), flush=True)
            with driver.session() as db:
                if db.run('MATCH (p:Product {product_id:$id}) RETURN count(p) AS count', id=pid).single()['count']:
                    raise ValueError('Reserved synthetic graph ProductID already exists')
                conflict = db.run('MATCH (n) WHERE any(key IN keys(n) WHERE key ENDS WITH "_id" AND n[key]=$id) RETURN count(n) AS count',
                                  id=taxonomy).single()['count']
                if conflict:
                    raise ValueError('Reserved synthetic taxonomy identity already exists')
            Base.metadata.create_all(engine)
            print(json.dumps({'stage': 'seeding_synthetic_product_and_outbox'}), flush=True)
            factory = sessionmaker(engine, expire_on_commit=False)
            with factory() as db, db.begin():
                for model in (Category, Material, Gemstone, Brand, Collection):
                    db.add(model(id=taxonomy, name='Synthetic projection ' + model.__name__))
                db.flush()
                db.add(Product(id=pid, sku='SYNTHETIC900020', barcode='900020', name='Synthetic projection product',
                               category_id=taxonomy, material_id=taxonomy, gemstone_id=taxonomy, brand_id=taxonomy,
                               collection_id=taxonomy, weight=1, sale_price=100, wholesale_price=80, cost_price=60, stock=10))
            encoder = Encoder()
            collection, _ = index_identity(model_name, revision, encoder.get_sentence_embedding_dimension())
            if server_url and vectors.collection_exists(collection):
                raise ValueError('The dedicated network Qdrant collection must not already exist')
            projection = ProductProjection(driver, 'neo4j', vectors, encoder, model_name, revision)
            now = datetime.now(timezone.utc)
            first = run_one(factory, projection, now=now)
            print(json.dumps({'stage': 'first_delivery_result', 'outcome': first}), flush=True)
            assert not first['delivered'] and first['error_type'] == 'TimeoutError'
            assert run_one(factory, projection, now=now + timedelta(seconds=3))['delivered']
            print(json.dumps({'stage': 'retry_delivered'}), flush=True)
            assert vectors.count(collection, exact=True).count == 1
            if server_url:
                query_vector = [float(value) for value in encoder.encode(['Synthetic projection product'])[0]]
                found = vectors.query_points(collection_name=collection, query=query_vector, limit=1).points
                assert len(found) == 1 and found[0].id == pid
            with factory() as db, db.begin():
                db.get(Product, pid).stock = 4
                db.get(Product, pid).sale_price = 120
            assert run_one(factory, projection)['delivered']
            with driver.session() as db:
                node = db.run('MATCH (p:Product {product_id:$id}) RETURN p.stock AS stock, p.sale_price AS price, p.is_deleted AS deleted', id=pid).single()
                assert node['stock'] == 4 and float(node['price']) == 120 and node['deleted'] is False
            with factory() as db, db.begin():
                db.delete(db.get(Product, pid))
            assert run_one(factory, projection)['delivered']
            assert vectors.count(collection, exact=True).count == 0
            with driver.session() as db:
                node = db.run('MATCH (p:Product {product_id:$id}) RETURN p.is_deleted AS deleted, p.stock AS stock', id=pid).single()
                assert node['deleted'] is True and node['stock'] == 0
            report = {'successful': True, 'business_database': 'actual isolated PostgreSQL',
                      'graph': 'actual isolated Neo4j', 'qdrant': 'actual container HTTP server' if server_url else 'actual in-memory engine',
                      'embedding': 'actual pinned MiniLM 384-dimensional; not a quality benchmark' if server_url else 'synthetic 3-dimensional; no model-quality claim',
                      'model_revision': revision, 'vector_dimension': encoder.get_sentence_embedding_dimension(),
                      'synthetic_product_id': pid, 'synthetic_taxonomy_id': taxonomy,
                      'checks': ['partial graph write retried', 'stable vector identity', 'live stock/price update',
                                 'product deletion graph tombstone and vector removal'],
                      'existing_500_catalog_product_ids_modified': False,
                      'production_accessed': False}
            with args.report.open('x', encoding='utf-8') as handle:
                json.dump(report, handle, indent=2)
            print(json.dumps(report))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
