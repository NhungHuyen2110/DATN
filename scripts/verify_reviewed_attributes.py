"""Real integration acceptance, exclusively on the named local QA services.

QA labels are synthetic test fixtures, never human ground truth or product claims.
No source database, serving graph/vector collection, or original user is changed.
Run through compose.review-acceptance.yaml; stdout is an aggregate JSON report.
"""
from contextlib import closing
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path[:0] = ['/srv', '/srv/backend', '/srv/AI']


def main():
    def progress(stage):
        print(json.dumps({'stage': stage, 'utc': datetime.now(timezone.utc).isoformat()}), file=sys.stderr, flush=True)
    progress('validate_isolated_targets')
    required = {
        'POSTGRES_HOST': 'postgres', 'POSTGRES_DB': 'lumiere_test_ai_acceptance',
        'BUSINESS_API_URL': 'http://business-qa:8001',
        'NEO4J_URI': 'bolt://neo4j-facts-qa:7687',
        'QDRANT_URL': 'http://qdrant-facts-qa:6333',
        'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED': 'true',
    }
    if any(os.getenv(key) != value for key, value in required.items()):
        raise ValueError('This acceptance requires the explicit isolated QA targets')
    from shared.recovery import validate_backup_reference
    validate_backup_reference('/qa/recovery/backup-reference.json', 'test', 'postgres', 5432,
                              'lumiere_test_ai_acceptance')
    import requests
    from neo4j import GraphDatabase
    from qdrant_client import QdrantClient
    from sqlalchemy import select
    from app.core.database import SessionLocal, engine
    from app.models.product_attribute_review import ProductAttributeReview
    from app.services.product_index_worker import current_product, run_one
    from app.models.product_index_job import ProductIndexJob
    from product_projection import ProductProjection
    from jewelry_agents.business_catalog import fetch_catalog
    from jewelry_agents.retrieval import (_search_qdrant, _graph_search_candidates,
        _graph_expand_candidates, extract_price_filter)
    from jewelry_agents.search_service import search
    from knowledge_graph.graph_writer import prepare_rows, verify_projection
    from knowledge_graph.graph_writer import import_projection
    from vector_index import index_identity, index_products

    cases = []
    base = required['BUSINESS_API_URL']
    prefix = 'local-qa-reviewed-attributes-fixture:'
    fixture = json.loads(Path('/qa/private/fixture.json').read_text())
    ids = [2, 79, 114]
    session = requests.Session()
    response = session.post(base + '/auth/login', json=fixture['accounts']['admin'], timeout=10)
    assert response.status_code == 200, 'QA admin login failed'
    assert session.get(base + '/admin/product-attributes/options', timeout=10).status_code == 200
    for pid in ids:
        endpoint = base + f'/admin/products/{pid}/verified-attributes'
        history = session.get(endpoint, timeout=10)
        assert history.status_code == 200
        rows = history.json()
        for label, canonical in [('Audience', 'female'), ('Style', 'elegant')]:
            old = next((row for row in rows if row['label'] == label and row['canonical_id'] == canonical), None)
            if old is not None:
                assert old['source_reference'].startswith(prefix), 'Refuse to alter non-fixture reviews'
            if pid == 79 and label == 'Style' and old is not None and old['active']:
                response = session.delete(endpoint + '/' + str(old['id']),
                    params={'expected_version':old['version']}, timeout=10)
                assert response.status_code == 204
                old = {**old, 'active':False}
            if old is None or not old['active']:
                response = session.post(endpoint, json={'label': label, 'canonical_id': canonical,
                    'source_reference': prefix + str(pid) + ':' + label,
                    'confirmed_review': True}, timeout=10)
                assert response.status_code == 200, 'QA attribute confirmation failed'
    cases.append('authenticated Admin confirmations persisted only in QA review store')
    live = fetch_catalog()
    assert len(live) == 500
    assert all(len(live[pid]['verified_attributes']) == 2 for pid in ids)
    assert all(set(fact) == {'label', 'canonical_id', 'name', 'source_reference_sha256'}
               for pid in ids for fact in live[pid]['verified_attributes'])
    cases.append('public catalog exposes canonical facts and evidence hashes without reviewer or raw notes')
    progress('load_pinned_offline_encoder')
    from sentence_transformers import SentenceTransformer
    unlabelled = next(pid for pid, product in live.items() if pid not in ids and product['CategoryID'] == 1
                     and not product.get('verified_attributes') and 0 < float(product['Price']) < 8_000_000)
    selected = ids + [unlabelled]
    revision = os.environ['EMBEDDING_REVISION']
    model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
    model_path = '/models/hub/models--sentence-transformers--' + model_name + '/snapshots/' + revision
    encoder = SentenceTransformer(model_path, device='cpu', local_files_only=True)
    with GraphDatabase.driver(required['NEO4J_URI'], auth=('neo4j', os.environ['NEO4J_PASSWORD']),
                              connection_timeout=5, max_transaction_retry_time=10) as driver, \
            closing(QdrantClient(url=required['QDRANT_URL'], timeout=10)) as qdrant:
        driver.verify_connectivity()
        projection = ProductProjection(driver, 'neo4j', qdrant, encoder, model_name, revision)
        def project(pids, bulk=False):
            with SessionLocal() as db:
                snapshots = [current_product(db, pid) for pid in pids]
            if bulk:
                digest = hashlib.sha256(json.dumps(snapshots, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                assert import_projection(driver, 'neo4j', snapshots, 'qa', digest)['pass']
                assert index_products(qdrant, encoder, snapshots, model_name, revision, digest, reuse_existing=True)['pass']
            else:
                for row in snapshots:
                    projection(row['ProductID'], row, 1)
            with driver.session() as graph:
                validation = verify_projection(graph, prepare_rows(snapshots, 'qa', '0' * 64))
            assert validation['pass'], 'Graph endpoint or evidence validation failed'
            return validation
        def counts():
            with driver.session() as graph:
                return dict(graph.run('MATCH (n) OPTIONAL MATCH (n)-[r]->() RETURN count(DISTINCT n) AS nodes, count(r) AS edges').single())
        def deliver_review_event(expected_ids):
            delivery = run_one(SessionLocal, projection)
            assert delivery['claimed'] and delivery['product_id'] in expected_ids
            assert delivery['delivered'] and delivery['acknowledged'] and delivery['error_type'] is None
            with SessionLocal() as db:
                job = db.get(ProductIndexJob, delivery['product_id'])
                assert job.status == 'done' and job.generation == job.delivered_generation
                assert job.lease_token is None
            return delivery
        first = project(selected, bulk=True)
        progress('initial_batch_projected')
        before = counts()
        project(selected, bulk=True)
        progress('batch_replay_verified')
        assert counts() == before
        with SessionLocal() as db:
            pending_ids = set(db.scalars(select(ProductIndexJob.product_id).where(ProductIndexJob.status != 'done')))
        assert pending_ids and pending_ids.issubset(ids), 'Refuse to claim non-fixture QA jobs'
        confirmation_deliveries = []
        for _ in range(len(pending_ids)):
            confirmation_deliveries.append(deliver_review_event(pending_ids))
            pending_ids.remove(confirmation_deliveries[-1]['product_id'])
        assert 79 in {item['product_id'] for item in confirmation_deliveries}
        cases.append('Admin HTTP confirmation atomically queued a real PostgreSQL outbox generation delivered and acknowledged by the worker core')
        cases.append('real Neo4j batch MERGE replay preserves node/edge counts and exact reviewed evidence')
        collection, _ = index_identity(model_name, revision, encoder.get_sentence_embedding_dimension())
        assert collection == os.environ['QDRANT_COLLECTION']
        points = qdrant.retrieve(collection, ids=selected, with_payload=True, with_vectors=False)
        assert len(points) == 4
        assert all(len(point.payload['verified_attributes']) == (2 if point.id in ids else 0) for point in points)
        cases.append('real 384-dimensional encoder indexes only canonical QA facts into separate Qdrant volume')
        dense = partial(_search_qdrant, services=(qdrant, encoder))
        graph = partial(_graph_search_candidates, driver=driver)
        expand = partial(_graph_expand_candidates, driver=driver)
        def run(query):
            return search(query, 3, dense, fetch_catalog, extract_price_filter,
                          graph=graph, graph_expander=expand, diagnostics=True)
        result = run('Top 3 nhẫn cho nữ thanh lịch dưới 8 triệu')
        progress('combined_query_returned')
        assert result['status'] == 'ok', 'Combined reviewed-attribute retrieval unavailable'
        assert {row['ProductID'] for row in result['products']} == set(ids)
        assert result['diagnostics']['source_ranks']['dense']
        assert all('dense' in row['retrieval_sources'] and row['graph_paths'] for row in result['products'])
        cases.append('real dense-anchor graph fusion returns exactly the three approved female elegant rings below 8m')
        related = run('Top 3 sản phẩm cùng phong cách với sản phẩm 2')
        progress('reference_query_returned')
        assert {row['ProductID'] for row in related['products']} == {79, 114}
        assert all(any(path['relationship'] == 'HAS_STYLE' and path['source_product_id'] == 2
                       for path in row['graph_paths']) for row in related['products'])
        cases.append('same-style traversal verifies evidence hashes on both reference and recommended products')
        endpoint = base + '/admin/products/79/verified-attributes'
        style = next(row for row in session.get(endpoint, timeout=10).json() if row['label'] == 'Style' and row['active'])
        response = session.delete(endpoint + '/' + str(style['id']), params={'expected_version': style['version']}, timeout=10)
        assert response.status_code == 204
        revocation_delivery = deliver_review_event({79})
        with SessionLocal() as db:
            revoked_snapshot = current_product(db, 79)
        with driver.session() as graph_session:
            assert verify_projection(graph_session, prepare_rows([revoked_snapshot], 'qa', '0' * 64))['pass']
        progress('revocation_projected')
        revoked = run('Top 3 nhẫn cho nữ thanh lịch dưới 8 triệu')
        assert {row['ProductID'] for row in revoked['products']} == {2, 114}
        assert counts() == before, 'Revocation must retain evidence edge history without duplicates'
        point = qdrant.retrieve(collection, ids=[79], with_payload=True, with_vectors=False)[0]
        assert [fact['label'] for fact in point.payload['verified_attributes']] == ['Audience']
        with driver.session() as graph_session:
            assert graph_session.run('MATCH (:Product {product_id:79})-[r:HAS_STYLE]->() RETURN r.active AS active').single()['active'] is False
        with SessionLocal() as db:
            audit = db.scalar(select(ProductAttributeReview).where(ProductAttributeReview.id == style['id']))
            assert audit.active is False and audit.version == style['version'] + 1
            assert audit.review_log[-1]['action'] == 'revoke'
        cases.append('revocation updates public filters, vector payload and inactive graph edge while retaining audited history')
        assert len(revoked['products']) == 2
        cases.append('Top-3 returns two eligible products without padding with unlabelled or revoked products')
    session.close()
    engine.dispose()
    report = {'successful': True, 'verified_utc': datetime.now(timezone.utc).isoformat(),
              'cases': cases, 'passed': len(cases), 'real_encoder': model_name, 'revision': revision,
              'graph_initial_validation': first, 'idempotent_graph_counts': before,
              'confirmation_worker_deliveries': confirmation_deliveries,
              'revocation_worker_delivery': revocation_delivery,
              'api_outbox_graph_vector_integration': True,
              'catalog_products': 500, 'indexed_qa_products': 4,
              'labels': 'synthetic QA fixture only; not human labels or real product claims',
              'serving_graph_vector_written': False, 'original_database_written': False,
              'real_model_quality': 'not_evaluated', 'llm': 'not_run'}
    print(json.dumps(report))


if __name__ == '__main__':
    main()
