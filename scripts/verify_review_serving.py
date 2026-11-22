"""Validate reviewed-fact activation on the local serving copy, without adding labels."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.host_process import run_bounded

INTERNAL = r'''
import json,os,sys
from pathlib import Path
sys.path[:0]=['/srv','/srv/AI']
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from shared.recovery import validate_backup_reference
from knowledge_graph.graph_writer import ensure_constraints,OWNER
from vector_index import index_identity
target=make_url(os.environ['LUMIERE_SYNC_DATABASE_URL'])
assert target.host=='postgres' and target.database=='lumiere_test_original_data'
assert os.environ.get('LUMIERE_ATTRIBUTE_REVIEWS_ENABLED')=='true'
assert os.environ['LUMIERE_SYNC_NEO4J_URI']=='bolt://neo4j:7687'
assert os.environ['LUMIERE_SYNC_QDRANT_URL']=='http://qdrant:6333'
validate_backup_reference('/recovery/backup-reference.json','test','postgres',5432,target.database)
engine=create_engine(target)
with engine.connect() as conn:
    conn.execute(text('SET TRANSACTION READ ONLY'))
    revision=conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    assert revision=='20261122_0010'
    ids=set(conn.execute(text('SELECT id FROM products')).scalars())
    reviews=conn.execute(text("SELECT count(*) AS total, count(*) FILTER (WHERE active) AS active, count(*) FILTER (WHERE source_reference LIKE 'local-qa-reviewed-attributes-fixture:%') AS qa FROM product_attribute_reviews")).mappings().one()
    reviews=dict(reviews)
    assert reviews['qa']==0
    jobs=dict(conn.execute(text('SELECT status,count(*) FROM product_index_jobs GROUP BY status')).all())
assert len(ids)==500 and jobs=={'done':500}
engine.dispose()
with GraphDatabase.driver(os.environ['LUMIERE_SYNC_NEO4J_URI'],auth=('neo4j',os.environ['LUMIERE_SYNC_GRAPH_PASSWORD']),connection_timeout=5,max_transaction_retry_time=10) as driver:
    with driver.session() as graph:
        graph_ids={r['id'] for r in graph.run('MATCH (p:Product {projection_owner:$owner}) RETURN p.product_id AS id',owner=OWNER)}
        assert graph_ids==ids
        assert graph.run('MATCH (p:Product) RETURN count(p) AS count').single()['count']==500
        schema=Path('/srv/AI/knowledge_graph/schema.cypher').read_text(encoding='utf-8-sig')
        statements='\n'.join(line for line in schema.splitlines() if not line.strip().startswith('//'))
        ensure_constraints(graph,statements)
        constraints=[r['name'] for r in graph.run('SHOW CONSTRAINTS YIELD name RETURN name')]
        assert len(constraints)==8
        graph_reviews=graph.run('MATCH (n) WHERE n:Audience OR n:Style RETURN count(n) AS count').single()['count']
client=QdrantClient(url=os.environ['LUMIERE_SYNC_QDRANT_URL'],timeout=5)
collection,_=index_identity('paraphrase-multilingual-MiniLM-L12-v2',os.environ['LUMIERE_SYNC_MODEL_REVISION'],384)
info=client.get_collection(collection)
assert info.points_count==500 and info.config.params.vectors.size==384
assert info.config.params.vectors.distance.value=='Cosine'
vector_ids=set();offset=None
for _ in range(10):
    points,offset=client.scroll(collection,limit=100,offset=offset,with_payload=False,with_vectors=False)
    vector_ids.update(point.id for point in points)
    if offset is None: break
assert vector_ids==ids
client.close()
print(json.dumps({'schema_revision':revision,'catalog_products':len(ids),'review_store':reviews,
    'outbox_states':jobs,'managed_graph_products':len(graph_ids),'graph_review_nodes':graph_reviews,
    'graph_constraints':sorted(constraints),'qdrant_products':len(vector_ids),
    'qdrant_collection':collection,'qdrant_dimension':384,'qdrant_metric':'Cosine',
    'new_labels_created':False,'graph_schema_only_added_constraints':True}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report path')
    def run(command, content=None):
        result = run_bounded(command, cwd=ROOT, input=content, timeout=150)
        if result.returncode:
            (ROOT / '.local-tmp/review-serving-check.private.log').write_bytes(result.stdout + result.stderr)
            raise RuntimeError('Serving review verification failed; inspect local log')
        return result.stdout.decode('utf-8')
    flags = {}
    for service in ('business-api', 'ai-api', 'index-worker'):
        details = json.loads(run(['docker', 'inspect', 'lumiere-rebuild-test-' + service + '-1']))[0]
        assert details['Config']['Labels']['com.docker.compose.project'] == 'lumiere-rebuild-test'
        env = dict(value.split('=', 1) for value in details['Config']['Env'] if '=' in value)
        flags[service] = env.get('LUMIERE_ATTRIBUTE_REVIEWS_ENABLED') == 'true'
    assert all(flags.values())
    internal = json.loads(run(['docker', 'exec', '-i', 'lumiere-rebuild-test-index-worker-1',
                               'python', '-B', '-'], INTERNAL.encode('utf-8')))
    base = 'http://127.0.0.1:18080'
    with urlopen(base + '/api/products?page_size=100', timeout=10) as response:
        catalog = json.load(response)
    assert catalog['total'] == 500
    assert all('verified_attributes' in product for product in catalog['items'])
    with urlopen(base + '/pages/admin/product-attributes.html', timeout=10) as response:
        assert 'admin-product-attributes.js' in response.read().decode('utf-8')
    try:
        urlopen(base + '/api/admin/product-attributes/options', timeout=10)
        raise AssertionError('Admin options exposed to anonymous visitor')
    except HTTPError as error:
        assert error.code == 401
    source = json.loads(run(['docker', 'inspect', 'lumiere-postgres']))[0]
    assert source['State']['Running'] is False
    report = {'successful': True, 'verified_utc': datetime.now(timezone.utc).isoformat(),
              'base_url': base, 'feature_flags': flags, **internal,
              'admin_page_served': True, 'anonymous_admin_options_status': 401,
              'original_source_still_stopped': True, 'original_source_written': False,
              'full_retrieval_validation': 'separate browser acceptance required',
              'llm_live_verified': False}
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
