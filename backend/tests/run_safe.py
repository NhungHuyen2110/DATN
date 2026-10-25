"""Run backend unittest discovery while forbidding real database connections."""

from pathlib import Path
import unittest
from unittest.mock import patch

import sqlalchemy as sa


class Result(unittest.TextTestResult):
    subtests_passed = 0

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is None:
            self.subtests_passed += 1


def main():
    original_connect = sa.engine.Engine.connect

    def memory_only(engine, *args, **kwargs):
        if engine.dialect.name != "sqlite" or engine.url.database != ":memory:":
            raise AssertionError("Only isolated in-memory SQLite connections are allowed")
        return original_connect(engine, *args, **kwargs)

    with patch.object(sa.engine.Engine, "connect", memory_only), patch("dotenv.load_dotenv"):
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent))
        result = unittest.TextTestRunner(verbosity=1, resultclass=Result).run(suite)
    print(f"Passed subtests: {result.subtests_passed}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
