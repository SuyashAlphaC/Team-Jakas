"""Static source localization with concrete patch proposals."""

from __future__ import annotations

import re
from pathlib import Path

from app.config_paths import ROOT
from app.models import RootCauseCandidate, Verdict

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


def _find_line(path: Path, pattern: str) -> int | None:
    if not path.exists():
        return None
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if re.search(pattern, line):
            return i
    return None


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

    patch = ""
    if line and spec.get("patch_from"):
        patch = (
            f"--- a/{spec['rel_path']}\n"
            f"+++ b/{spec['rel_path']}\n"
            f"@@ -{line},1 +{line},1 @@\n"
            f"-{spec['patch_from']}\n"
            f"+{spec['patch_to']}"
        )

    cause_map = {
        "attack": "malicious",
        "internal_fault_process": "code_config",
        "internal_fault_transaction": "code_config",
    }

    from app.models import CauseClass

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


def localize_from_verdict(domain: str, verdict: Verdict, evidence: list[str]) -> RootCauseCandidate | None:
    if verdict == Verdict.ATTACK:
        return localize("attack", evidence)
    if verdict == Verdict.INTERNAL_FAULT:
        if domain == "process":
            return localize("internal_fault_process", evidence)
        return localize("internal_fault_transaction", evidence)
    return None
