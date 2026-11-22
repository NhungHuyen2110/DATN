"""Bound one read-only retrieval task per source, timeout callers, and back off failed probes.

Late results are discarded. A timed-out task may finish in its single worker;
new callers never enqueue more work while it is running. No writes or retries
are performed by this component.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextvars import copy_context
import threading
import time


class SourceUnavailable(RuntimeError):
    pass


class SourceGate:
    def __init__(self, name, timeout=3, cooldown=15, clock=time.monotonic):
        if timeout <= 0 or cooldown < 0:
            raise ValueError('Positive timeout and nonnegative cooldown required')
        self.timeout, self.cooldown, self.clock = timeout, cooldown, clock
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='lumiere-' + name)
        self._future, self._open_until, self._closed = None, 0, False
        self._caller_finished = True

    def call(self, function, *args, **kwargs):
        with self._lock:
            if self._closed or self.clock() < self._open_until:
                raise SourceUnavailable('Source is cooling down')
            if self._future is not None and (not self._caller_finished or not self._future.done()):
                raise SourceUnavailable('Source already has a retrieval in flight')
            context = copy_context()
            future = self._pool.submit(context.run, function, *args, **kwargs)
            self._future = future
            self._caller_finished = False
        try:
            result = future.result(timeout=self.timeout)
        except FutureTimeout:
            with self._lock:
                self._open_until = self.clock() + self.cooldown
            raise SourceUnavailable('Retrieval exceeded its source time budget') from None
        except Exception:
            with self._lock:
                self._open_until = self.clock() + self.cooldown
            raise
        else:
            with self._lock:
                self._open_until = 0
            return result
        finally:
            with self._lock:
                if self._future is future:
                    self._caller_finished = True

    def close(self):
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)
