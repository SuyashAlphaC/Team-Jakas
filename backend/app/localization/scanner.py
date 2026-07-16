"""Static source localization with stack-trace parsing and patch proposals."""

from __future__ import annotations

import re
from pathlib import Path

from app.config_paths import ROOT
from app.localization.stacktrace import (
    ParsedStackTrace,
    StackFrame,
    extract_stack_from_evidence,
    normalize_stack_text,
    parse_stack_trace,
)
from app.models import CauseClass, RootCauseCandidate, Verdict

LOCALIZATION_MAP = {
    "attack": {
        "service": "identity",
        "rel_path": "services/identity-svc/auth_handler.py",
        "function": "validate_credentials",
        "config_key": "RATE_LIMIT_PER_ASN",
        "likely_commit": "abc123f",
        "search_patterns": [r"RATE_LIMIT_PER_ASN = \d+", r"def validate_credentials"],
        "patch_from": "RATE_LIMIT_PER_ASN = 999999",
        "patch_to": "RATE_LIMIT_PER_ASN = 100  # per-ASN cap during events",
        "mechanism": "Credential-stuffing during merch drop: 54%+ auth failures with no identity context scope.",
        "proposed_fix": "Rate-limit /auth/login per ASN; enable CAPTCHA; WAF block top /24 subnets.",
    },
    "internal_fault_process": {
        "service": "identity_svc",
        "rel_path": "services/identity-svc/memory_leak.py",
        "function": "authenticate",
        "config_key": None,
        "likely_commit": "def456a",
        "search_patterns": [r"_heap\.append\(b\"x\" \* 65536\)"],
        "patch_from": '_heap.append(b"x" * 65536)',
        "patch_to": "# Fixed: removed per-request heap allocation leak",
        "mechanism": "Memory leak: 64KB allocated per auth attempt without release; monotonic heap growth.",
        "proposed_fix": "Remove leak; add heap cap; rolling restart + route to warm standby pool.",
    },
    "internal_fault_transaction": {
        "service": "payment",
        "rel_path": "services/payment-svc/retry.py",
        "function": "process_payment",
        "config_key": "MAX_RETRIES",
        "likely_commit": "ghi789b",
        "search_patterns": [r"MAX_RETRIES = \d+", r"while attempts < MAX_RETRIES"],
        "patch_from": "MAX_RETRIES = 999",
        "patch_to": "MAX_RETRIES = 3  # capped; was 999 causing retry storm",
        "mechanism": "Retry storm: max_retries=999 with 800ms timeout and no backoff triggers client cascade.",
        "proposed_fix": "Cap retries to 3; exponential backoff; circuit breaker on payment-svc.",
    },
}

_CAUSE_BY_VERDICT = {
    Verdict.ATTACK: CauseClass.MALICIOUS,
    Verdict.INTERNAL_FAULT: CauseClass.CODE_CONFIG,
}


def _find_line(path: Path, pattern: str) -> int | None:
    if not path.exists():
        return None
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if re.search(pattern, line):
            return i
    return None


def _map_key(domain: str, verdict: Verdict) -> str | None:
    if verdict == Verdict.ATTACK:
        return "attack"
    if verdict == Verdict.INTERNAL_FAULT:
        return "internal_fault_process" if domain == "process" else "internal_fault_transaction"
    return None


def _spec_for_path(rel_path: str) -> dict | None:
    for spec in LOCALIZATION_MAP.values():
        if spec["rel_path"] == rel_path:
            return spec
    return None


def _service_from_path(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "services":
        return parts[1].replace("-", "_")
    return "unknown"


def _build_patch(rel_path: str, line: int, spec: dict | None) -> tuple[str, str]:
    abs_path = ROOT / rel_path
    if not abs_path.exists():
        return "", ""
    lines = abs_path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return "", ""
    content = lines[line - 1]
    if spec and spec.get("patch_from") and spec["patch_from"] in content:
        patch = (
            f"--- a/{rel_path}\n"
            f"+++ b/{rel_path}\n"
            f"@@ -{line},1 +{line},1 @@\n"
            f"-{spec['patch_from']}\n"
            f"+{spec['patch_to']}"
        )
        return patch, spec["proposed_fix"]
    patch = (
        f"--- a/{rel_path}\n"
        f"+++ b/{rel_path}\n"
        f"@@ -{line},1 +{line},1 @@\n"
        f"-{content.rstrip()}\n"
        f"+# TODO: fix root cause at stack frame {line}"
    )
    return patch, f"Review and fix `{rel_path}:{line}` surfaced in production stack trace."


def _root_from_frame(
    frame: StackFrame,
    verdict: Verdict,
    domain: str,
    evidence: list[str],
    parsed: ParsedStackTrace,
    confidence: float,
) -> RootCauseCandidate:
    rel = frame.rel_path()
    spec = _spec_for_path(rel)
    patch, fix_text = _build_patch(rel, frame.line, spec)

    mechanism = spec["mechanism"] if spec else f"Stack trace implicates `{rel}`"
    if parsed.exception_type:
        mechanism = f"{parsed.exception_type}: {mechanism}"
        if parsed.exception_message:
            mechanism += f" ({parsed.exception_message})"

    stack_evidence = [
        f"stack frame: {frame.file_ref()}"
        + (f" in {frame.function}()" if frame.function else ""),
        f"parser: {parsed.language} ({len(parsed.frames)} frames, {len(parsed.project_frames())} in services/)",
    ]

    proposed = fix_text
    if patch:
        proposed += f"\n\n```diff\n{patch}\n```"

    return RootCauseCandidate(
        service=spec["service"] if spec else _service_from_path(rel),
        cause_class=_CAUSE_BY_VERDICT.get(verdict, CauseClass.CODE_CONFIG),
        confidence=confidence,
        file=frame.file_ref(),
        function=frame.function or (spec["function"] if spec else None),
        config_key=spec.get("config_key") if spec else None,
        likely_commit=spec.get("likely_commit") if spec else None,
        mechanism=mechanism,
        proposed_fix=proposed,
        evidence=stack_evidence + list(evidence),
    )


def localize_from_stack(
    stack_text: str,
    verdict: Verdict,
    domain: str,
    evidence: list[str],
    confidence: float = 0.85,
) -> list[RootCauseCandidate]:
    """Build root-cause candidates from parsed stack frames (prefer services/ paths)."""
    parsed = parse_stack_trace(stack_text)
    if not parsed.frames:
        return []

    project = parsed.project_frames()
    frames = project if project else [parsed.best_frame]  # type: ignore[list-item]

    roots: list[RootCauseCandidate] = []
    seen_files: set[str] = set()
    for frame in frames:
        rel = frame.rel_path()
        if rel in seen_files:
            continue
        seen_files.add(rel)
        roots.append(_root_from_frame(frame, verdict, domain, evidence, parsed, confidence))
    return roots


def localize(verdict_key: str, evidence: list[str]) -> RootCauseCandidate:
    spec = LOCALIZATION_MAP[verdict_key]
    abs_path = ROOT / spec["rel_path"]
    line = None
    for pat in spec["search_patterns"]:
        line = _find_line(abs_path, pat)
        if line:
            break

    file_ref = spec["rel_path"]
    if line:
        file_ref = f"{spec['rel_path']}:{line}"

    patch, _ = _build_patch(spec["rel_path"], line or 1, spec)

    cause_map = {
        "attack": "malicious",
        "internal_fault_process": "code_config",
        "internal_fault_transaction": "code_config",
    }

    return RootCauseCandidate(
        service=spec["service"],
        cause_class=CauseClass(cause_map[verdict_key]),
        confidence=0.85,
        file=file_ref,
        function=spec["function"],
        config_key=spec["config_key"],
        likely_commit=spec["likely_commit"],
        mechanism=spec["mechanism"],
        proposed_fix=spec["proposed_fix"] + (f"\n\n```diff\n{patch}\n```" if patch else ""),
        evidence=evidence,
    )


def localize_from_verdict(
    domain: str,
    verdict: Verdict,
    evidence: list[str],
    *,
    stack_text: str | None = None,
    confidence: float = 0.85,
) -> RootCauseCandidate | None:
    if verdict not in (Verdict.ATTACK, Verdict.INTERNAL_FAULT):
        return None

    raw_stack = stack_text or extract_stack_from_evidence(evidence)
    if raw_stack:
        roots = localize_from_stack(normalize_stack_text(raw_stack), verdict, domain, evidence, confidence)
        if roots:
            return roots[0]

    key = _map_key(domain, verdict)
    return localize(key, evidence) if key else None


def localize_all_from_verdict(
    domain: str,
    verdict: Verdict,
    evidence: list[str],
    *,
    stack_text: str | None = None,
    confidence: float = 0.85,
) -> list[RootCauseCandidate]:
    """All unique roots for a verdict — multiple stack frames or single map fallback."""
    if verdict not in (Verdict.ATTACK, Verdict.INTERNAL_FAULT):
        return []

    raw_stack = stack_text or extract_stack_from_evidence(evidence)
    if raw_stack:
        roots = localize_from_stack(normalize_stack_text(raw_stack), verdict, domain, evidence, confidence)
        if roots:
            return roots

    key = _map_key(domain, verdict)
    if key:
        return [localize(key, evidence)]
    return []
