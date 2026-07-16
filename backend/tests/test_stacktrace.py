"""Tests for stack trace parsing and stack-first localization."""

from pathlib import Path

from app.analysis.fusion import fuse_observation
from app.ingestion.csv_adapter import load_observations
from app.ingestion.stack_traces import attach_stack_traces
from app.localization.scanner import localize_all_from_verdict, localize_from_verdict
from app.localization.stacktrace import parse_stack_trace
from app.models import Verdict
from app.rca.engine import build_incident

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

PYTHON_TRACE = """Traceback (most recent call last):
  File "services/payment-svc/retry.py", line 14, in process_payment
    raise TimeoutError("payment timeout after 800ms")
  File "services/identity-svc/memory_leak.py", line 9, in authenticate
    _heap.append(b"x" * 65536)
TimeoutError: payment timeout after 800ms"""

JAVA_TRACE = """java.lang.RuntimeException: checkout failed
\tat com.sphere.payment.Retry.processPayment(Retry.java:14)
\tat com.sphere.checkout.CheckoutController.submit(CheckoutController.java:88)"""

GO_TRACE = """panic: heap exhausted
goroutine 42 [running]:
services/identity-svc/memory_leak.go:9 +0x4a"""


def test_parse_python_frames():
    parsed = parse_stack_trace(PYTHON_TRACE)
    assert parsed.exception_type == "TimeoutError"
    assert len(parsed.project_frames()) == 2
    assert parsed.best_frame.file_ref() == "services/identity-svc/memory_leak.py:9"
    assert parsed.best_frame.function == "authenticate"


def test_parse_java_frame():
    parsed = parse_stack_trace(JAVA_TRACE)
    assert parsed.frames
    assert parsed.frames[0].line == 14
    assert parsed.frames[0].function == "processPayment"


def test_parse_go_frame():
    parsed = parse_stack_trace(GO_TRACE)
    assert parsed.project_frames()[0].file_ref().endswith("memory_leak.go:9")


def test_localize_prefers_stack_over_map():
    roots = localize_all_from_verdict(
        "transaction",
        Verdict.INTERNAL_FAULT,
        ["retry storm"],
        stack_text=PYTHON_TRACE,
    )
    files = {r.file for r in roots}
    assert "services/payment-svc/retry.py:14" in files
    assert "services/identity-svc/memory_leak.py:9" in files
    assert any("stack frame:" in e for r in roots for e in r.evidence)


def test_fixture_stack_traces_attach_to_seed():
    obs_list = load_observations(FIXTURES / "dataset_seed.csv")
    attach_stack_traces(obs_list, FIXTURES)
    t16 = next(o for o in obs_list if o.timestamp.endswith("20:16:00Z"))
    assert "stack_trace" in t16.labels
    assert "retry.py" in t16.labels["stack_trace"]


def test_incident_roots_from_stack_at_t16():
    obs_list = load_observations(FIXTURES / "dataset_seed.csv")
    attach_stack_traces(obs_list, FIXTURES)
    history = []
    incident = None
    for obs in obs_list:
        fusion = fuse_observation(obs, history)
        history.append(obs)
        alerts = [v for v in fusion.domain_verdicts if v.verdict in (Verdict.ATTACK, Verdict.INTERNAL_FAULT)]
        if alerts:
            incident = build_incident("inc-test", obs, fusion.domain_verdicts, detect_ms=10.0)
    assert incident is not None
    files = [r.file for r in incident.roots if r.file]
    assert any("retry.py" in f or "memory_leak.py" in f or "auth_handler.py" in f for f in files)
    assert any("stack frame:" in e for r in incident.roots for e in r.evidence)


def test_fallback_map_when_no_stack():
    root = localize_from_verdict("process", Verdict.INTERNAL_FAULT, ["heap growth"])
    assert root is not None
    assert "memory_leak.py" in (root.file or "")
