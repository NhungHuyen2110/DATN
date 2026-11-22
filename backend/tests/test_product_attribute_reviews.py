"""Review permissions, evidence and atomic outbox on isolated memory fixtures."""
import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
import test_orders_api as fixtures


@pytest.fixture
def review_case():
    fixtures.OrderTests.setUpClass()
    case=fixtures.OrderTests()
    case.setUp()
    try:
        with patch.dict(os.environ,{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            yield case,TestClient(case.app)
    finally:
        case.doCleanups()
        fixtures.OrderTests.tearDownClass()


def payload():
    return {'label':'Style','canonical_id':'elegant','source_reference':'QA fixture evidence only',
            'confirmed_review':True}


def test_reviews_require_admin_and_explicit_valid_evidence(review_case):
    _,client=review_case
    route='/admin/products/1/verified-attributes'
    for token,status in ((None,401),('test-token',403),('staff-token',403)):
        cookies={} if token is None else {'lumiere_session':token}
        assert client.post(route,json=payload(),cookies=cookies).status_code==status
    for changes in ({'confirmed_review':False},{'canonical_id':'invented'}, {'source_reference':'  '}):
        assert client.post(route,json={**payload(),**changes},cookies={'lumiere_session':'admin-token'}).status_code==422


def test_review_revoke_preserves_history_and_queues_sync_atomically(review_case):
    case,client=review_case
    from app.models.product_index_job import ProductIndexJob
    route='/admin/products/1/verified-attributes'
    cookies={'lumiere_session':'admin-token'}
    with patch.dict(os.environ,{'PRODUCT_INDEX_SYNC_ENABLED':'true'}):
        response=client.post(route,json=payload(),cookies=cookies)
        assert response.status_code==200
        review=response.json()
        assert review['reviewed_by']==3 and len(review['review_log'])==1
        assert len(review['source_reference_sha256'])==64
        assert client.post(route,json=payload(),cookies=cookies).status_code==409
        target=route+'/'+str(review['id'])
        assert client.delete(target+'?expected_version=2',cookies=cookies).status_code==409
        assert client.delete(target+'?expected_version=1',cookies=cookies).status_code==204
        rows=client.get(route,cookies=cookies).json()
        assert not rows[0]['active'] and len(rows[0]['review_log'])==2
        assert client.post(route,json=payload(),cookies=cookies).status_code==200
    with Session(case.engine) as db:
        job=db.scalar(select(ProductIndexJob).where(ProductIndexJob.product_id==1))
        assert job.generation==3
        assert db.get(case.Product,1).stock==5
