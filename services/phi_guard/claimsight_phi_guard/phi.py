"""PHI/PII redaction before any model call. Re-id map is for authorized UI only."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
MRN_RE = re.compile(r"\bMRN[- ]?\d{6,12}\b", re.I)
DOB_RE = re.compile(r"\b(?:DOB|date of birth)\s*[:\-]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b")
ADDRESS_RE = re.compile(
    r"\b\d+\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Road|Street|Lane|Avenue|Drive|Way|Blvd)\b",
    re.I,
)
BARE_NAME_RE = re.compile(
    r"\b(Elena Vasquez|Marcus Chen|Priya Shah|James Okonkwo|"
    r"Aisha Rahman|Robert Hale|Nina Patel|David Okada)\b"
)
INJECTION_RE = re.compile(
    r"(ignore (?:previous|all) instructions|you are now|system prompt|"
    r"exfiltrate|reveal (?:the )?(?:ssn|mrn|api key))",
    re.I,
)


def _tok(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()[:10]
    return f"[{kind.upper()}_{digest}]"


@dataclass
class RedactionResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    injection_hits: list[str] = field(default_factory=list)


class PhiGuard:
    """De-identify before inference. Vault mapping never goes to the model layer."""

    def redact_text(self, text: str | None) -> RedactionResult:
        if not text:
            return RedactionResult(text="")
        mapping: dict[str, str] = {}
        findings: list[str] = []
        out = text

        def sub(pattern: re.Pattern[str], kind: str, src: str) -> str:
            def repl(m: re.Match[str]) -> str:
                raw = m.group(0)
                token = _tok(kind, raw)
                mapping[token] = raw
                findings.append(kind)
                return token

            return pattern.sub(repl, src)

        out = sub(SSN_RE, "ssn", out)
        out = sub(MRN_RE, "mrn", out)
        out = sub(DOB_RE, "dob", out)
        out = sub(EMAIL_RE, "email", out)
        out = sub(PHONE_RE, "phone", out)
        out = sub(ADDRESS_RE, "address", out)
        out = BARE_NAME_RE.sub(lambda m: self._name(m.group(0), mapping, findings), out)
        injections = [m.group(0) for m in INJECTION_RE.finditer(text)]
        return RedactionResult(
            text=out, mapping=mapping, findings=findings, injection_hits=injections
        )

    def _name(self, raw: str, mapping: dict[str, str], findings: list[str]) -> str:
        token = _tok("patient_name", raw)
        mapping[token] = raw
        findings.append("name")
        return token

    def redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.redact_text(obj).text
        if isinstance(obj, list):
            return [self.redact_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.redact_obj(v) for k, v in obj.items()}
        return obj

    def rehydrate(self, text: str, mapping: dict[str, str]) -> str:
        out = text
        for token, raw in mapping.items():
            out = out.replace(token, raw)
        return out

    def scan_for_leak(self, text: str) -> list[str]:
        hits: list[str] = []
        if SSN_RE.search(text):
            hits.append("ssn")
        if MRN_RE.search(text):
            hits.append("mrn")
        if EMAIL_RE.search(text):
            hits.append("email")
        if BARE_NAME_RE.search(text):
            hits.append("name")
        if PHONE_RE.search(text):
            hits.append("phone")
        return hits

    def scan_injection(self, text: str) -> list[str]:
        return [m.group(0) for m in INJECTION_RE.finditer(text or "")]
