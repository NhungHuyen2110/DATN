from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, InterfaceError, TimeoutError, IntegrityError
from app.main import app
from app.core.database import get_db, engine


@pytest.mark.parametrize('failure', [
    OperationalError('synthetic SQL', {}, Exception('private-canary')),
    InterfaceError('synthetic SQL', {}, Exception('private-canary')),
    TimeoutError('private-canary'),
])
def test_database_connection_failures_are_controlled_and_do_not_leak_details(failure):
    def unavailable():
        raise failure
        yield  # FastAPI generator dependency; no real connection is opened.
    with patch.dict(app.dependency_overrides, {get_db: unavailable}):
        response = TestClient(app).get('/products')
    assert response.status_code == 503
    assert response.headers['Retry-After'] == '5'
    assert 'private-canary' not in response.text
    assert 'synthetic SQL' not in response.text


def test_integrity_errors_are_not_misclassified_as_connection_outages():
    def integrity_failure():
        raise IntegrityError('synthetic SQL', {}, Exception('constraint'))
        yield
    with patch.dict(app.dependency_overrides, {get_db: integrity_failure}):
        with pytest.raises(IntegrityError):
            TestClient(app).get('/products')


def test_postgres_connection_and_pool_wait_have_finite_budgets():
    # Engine connect_args are applied at connection time; inspect the creator
    # closure rather than connecting to any real database.
    with patch.object(engine.dialect, 'connect', side_effect=OperationalError('', {}, Exception('offline'))) as connect:
        with pytest.raises(OperationalError):
            engine.pool._creator()
    assert 1 <= connect.call_args.kwargs['connect_timeout'] <= 30
    assert 1 <= engine.pool.timeout() <= 30
