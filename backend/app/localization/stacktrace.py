"""Parse production stack traces into file:line localization."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.config_paths import ROOT

# Python: File "path", line 14, in process_payment
_PY_FRAME = re.compile(
    r'File\s+"(?P<path>[^"]+)"\s*,\s*line\s+(?P<line>\d+)(?:\s*,\s*in\s+(?P<func>[^\n]+))?',
)
_PY_FRAME_BARE = re.compile(
    r'File\s+(?P<path>[^\s,]+)\s*,\s*line\s+(?P<line>\d+)(?:\s*,\s*in\s+(?P<func>[^\n]+))?',
)

# Java / Kotlin: at com.foo.Bar.method(Bar.java:42)
_JAVA_FRAME = re.compile(
    r"at\s+(?P<qualifier>[\w.$]+)\.(?P<func>[\w$]+)\((?P<file>[\w.$]+):(?P<line>\d+)\)",
)

# Go: services/payment-svc/retry.go:42 +0x1a2
_GO_FRAME = re.compile(
    r"(?P<path>[\w./_-]+\.(?:go|rs)):(?P<line>\d+)",
)

# Node/V8: at processPayment (/app/services/payment-svc/retry.js:14:11)
_NODE_FRAME = re.compile(
    r"at\s+(?P<func>[\w.<>\[\]]+)\s+\((?P<path>[^:)]+):(?P<line>\d+):(?P<col>\d+)\)",
)

_EXCEPTION_LINE = re.compile(
    r"^(?P<exc>[\w.]+(?:Error|Exception)):\s*(?P<msg>.+)$",
    re.MULTILINE,
)


@dataclass
class StackFrame:
    path: str
    line: int
    function: str | None = None
    language: str = "unknown"
    raw: str = ""

    def rel_path(self) -> str:
        p = self.path.replace("\\", "/")
        if p.startswith(str(ROOT).replace("\\", "/")):
            return str(Path(p).relative_to(ROOT)).replace("\\", "/")
        root_marker = "/services/"
        idx = p.find(root_marker)
        if idx >= 0:
            return p[idx + 1 :]
        if p.startswith("services/"):
            return p
        return p.lstrip("/")

    def file_ref(self) -> str:
        rel = self.rel_path()
        return f"{rel}:{self.line}"


@dataclass
class ParsedStackTrace:
    frames: list[StackFrame] = field(default_factory=list)
    exception_type: str | None = None
    exception_message: str | None = None
    language: str = "unknown"

    def project_frames(self) -> list[StackFrame]:
        """Frames under repo services/ — deepest (most specific) last."""
        project = [f for f in self.frames if f.rel_path().startswith("services/")]
        return project

    @property
    def best_frame(self) -> StackFrame | None:
        project = self.project_frames()
        if project:
            return project[-1]
        return self.frames[-1] if self.frames else None


def normalize_stack_text(text: str) -> str:
    """Unescape CSV pipe separators and literal \\n."""
    t = text.strip()
    if not t:
        return ""
    if "|" in t and ("Traceback" in t or " at " in t):
        t = t.replace("|", "\n")
    t = t.replace("\\n", "\n")
    return t


def parse_stack_trace(text: str) -> ParsedStackTrace:
    """Parse Python, Java, Go, or Node stack traces."""
    normalized = normalize_stack_text(text)
    if not normalized:
        return ParsedStackTrace()

    result = ParsedStackTrace()
    seen: set[tuple[str, int, str | None]] = set()

    for m in _EXCEPTION_LINE.finditer(normalized):
        result.exception_type = m.group("exc")
        result.exception_message = m.group("msg").strip()
        break

    def add(path: str, line: int, func: str | None, lang: str, raw: str) -> None:
        path = path.replace("\\", "/")
        key = (path, line, func)
        if key in seen:
            return
        seen.add(key)
        result.frames.append(
            StackFrame(path=path, line=line, function=func, language=lang, raw=raw.strip()),
        )
        if result.language == "unknown":
            result.language = lang

    for m in _PY_FRAME.finditer(normalized):
        add(m.group("path"), int(m.group("line")), (m.group("func") or "").strip() or None, "python", m.group(0))
    for m in _PY_FRAME_BARE.finditer(normalized):
        add(m.group("path"), int(m.group("line")), (m.group("func") or "").strip() or None, "python", m.group(0))
    for m in _JAVA_FRAME.finditer(normalized):
        add(m.group("file"), int(m.group("line")), m.group("func"), "java", m.group(0))
    for m in _GO_FRAME.finditer(normalized):
        add(m.group("path"), int(m.group("line")), None, "go", m.group(0))
    for m in _NODE_FRAME.finditer(normalized):
        add(m.group("path"), int(m.group("line")), m.group("func"), "node", m.group(0))

    return result


def extract_stack_from_evidence(evidence: list[str]) -> str | None:
    """Find embedded stack trace text in evidence strings."""
    for item in evidence:
        if "Traceback (most recent call last)" in item:
            return item
        if re.search(r"\n\s+at\s+[\w.]+", item):
            return item
        if "File \"" in item and ", line " in item:
            return item
    return None
