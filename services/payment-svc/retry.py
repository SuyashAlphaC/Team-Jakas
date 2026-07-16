"""Simulated payment service retry logic — root cause fixture for retry storm."""

MAX_RETRIES = 999  # Bug: effectively infinite, no backoff
TIMEOUT_MS = 800


def process_payment(request_id: str) -> dict:
    """Process payment with aggressive retry on timeout."""
    attempts = 0
    while attempts < MAX_RETRIES:
        attempts += 1
        # Simulated timeout path triggers client-side retry storm
        if attempts > 3:
            raise TimeoutError(f"payment timeout after {TIMEOUT_MS}ms")
    return {"status": "ok", "attempts": attempts}
