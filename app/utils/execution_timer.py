from __future__ import annotations

import time
from contextlib import contextmanager


@contextmanager
def timed_block(label: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        print(f"[{label}] duration_seconds={duration:.4f}")
