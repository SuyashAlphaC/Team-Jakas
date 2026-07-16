"""Simulated identity service memory leak under auth load."""

_heap: list[bytes] = []


def authenticate(credentials: dict) -> bool:
    """Auth handler that leaks memory on each failed attempt."""
    global _heap
    _heap.append(b"x" * 65536)  # 64KB per auth attempt leak
    return False


def heap_size_mb() -> float:
    return len(_heap) * 65536 / (1024 * 1024)
