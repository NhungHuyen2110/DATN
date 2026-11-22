import asyncio
import unittest
from unittest.mock import patch


class BusinessShutdownTests(unittest.TestCase):
    def test_pool_disposal_runs_on_normal_or_exceptional_shutdown_without_connecting(self):
        from app.main import lifespan
        for fail in (False, True):
            with self.subTest(fail=fail), patch('app.main.engine.dispose') as dispose, patch('app.main.engine.connect') as connect:
                async def exercise():
                    try:
                        async with lifespan(None):
                            if fail:
                                raise RuntimeError('synthetic shutdown')
                    except RuntimeError:
                        pass
                asyncio.run(exercise())
                dispose.assert_called_once()
                connect.assert_not_called()
