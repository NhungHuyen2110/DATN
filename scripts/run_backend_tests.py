"""Run both pytest and unittest-style backend tests with DB/network guards.

No application import occurs before the guards. Requires pytest and backend deps.
Temporary files/cache belong on D; does not read .env or use real credentials.
"""
from contextlib import ExitStack
import os
from pathlib import Path
import socket
import sys
import threading
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def main():
    import sqlalchemy as sa
    import pytest

    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Offline tests permit only SQLite :memory:")
        return original_connect(engine, *args, **kwargs)

    original_socketpair = socket.socketpair
    original_socket_connect = socket.socket.connect
    local = threading.local()

    def internal_socketpair(*args, **kwargs):
        # Windows asyncio uses a loopback socketpair for its internal wakeup pipe.
        # Permit connections only inside this stdlib call on the same thread.
        local.creating_socketpair = True
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            local.creating_socketpair = False

    def no_network(sock, *args, **kwargs):
        if getattr(local, "creating_socketpair", False):
            return original_socket_connect(sock, *args, **kwargs)
        raise AssertionError("Offline backend baseline forbids network connections")

    # Force deterministic test configuration; never inherit real DB credentials.
    test_env = {"POSTGRES_DB": "lumiere_offline_tests", "POSTGRES_PASSWORD": "test_placeholder",
                "PRODUCT_INDEX_SYNC_ENABLED": "false",
                "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "1", "POSTGRES_USER": "test_only",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / "backend"))
    os.chdir(ROOT / "backend")
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, test_env))
        stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
        stack.enter_context(patch.object(sa.engine.Engine, "connect", memory_only))
        stack.enter_context(patch.object(socket.socket, "connect", no_network))
        stack.enter_context(patch.object(socket.socket, "connect_ex", no_network))
        stack.enter_context(patch.object(socket, "socketpair", internal_socketpair))
        # Fail closed before collecting application tests if isolation regresses.
        file_engine = sa.create_engine("sqlite:///must-not-be-created.db")
        try:
            file_engine.connect()
        except AssertionError:
            pass
        else:
            raise AssertionError("File database guard failed")
        finally:
            file_engine.dispose()
        with socket.socket() as connection:
            try:
                connection.connect(("127.0.0.1", 1))
            except AssertionError:
                pass
            else:
                raise AssertionError("Network guard failed")
        memory_engine = sa.create_engine("sqlite:///:memory:")
        try:
            with memory_engine.connect() as connection:
                assert connection.exec_driver_sql("SELECT 1").scalar() == 1
        finally:
            memory_engine.dispose()
        left, right = socket.socketpair()
        try:
            left.sendall(b"ok")
            assert right.recv(2) == b"ok"
        finally:
            left.close()
            right.close()
        print("Guard canaries passed: file DB blocked; network blocked; memory DB and internal socketpair allowed")
        return pytest.main(["tests", "-p", "no:cacheprovider", "--tb=short", "-q", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
