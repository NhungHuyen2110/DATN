
"""Run coupon regression tests with isolated test settings."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(PROJECT_DIR / ".env")

# Do not run without an explicitly designated test database.
db_name = os.getenv("POSTGRES_DB", "")
if db_name != "lumiere_backend_test":
    raise SystemExit(
        "STOP: POSTGRES_DB must be lumiere_backend_test"
    )

# Preserve default shipping assumptions of legacy coupon tests.
os.environ["SHIPPING_FLAT_VND"] = "0"
os.environ["SHIPPING_FREE_FROM_VND"] = "2000000"

os.chdir(BACKEND_DIR)

raise SystemExit(
    pytest.main([
        "tests/test_coupons_api.py",
        "-q",
        "--tb=short",
    ])
)
