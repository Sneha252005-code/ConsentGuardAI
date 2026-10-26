import re
from dataclasses import dataclass


@dataclass
class FilterResult:
    allowed: bool
    reason: str = ""


SENSITIVE_PATTERNS = [
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"),
]

INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior) instructions", re.IGNORECASE),
    re.compile(r"reveal (the )?(system prompt|hidden instructions)", re.IGNORECASE),
    re.compile(r"bypass (the )?(security|authorization|access control)", re.IGNORECASE),
]


def filter_prompt(prompt: str) -> FilterResult:
    """Check a prompt for common sensitive-data patterns and injection phrases."""
    if not isinstance(prompt, str) or not prompt.strip():
        return FilterResult(False, "Prompt is empty or invalid.")

    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(prompt):
            return FilterResult(
                False,
                "Prompt may contain sensitive information."
            )

    for pattern in INJECTION_PATTERNS:
        if pattern.search(prompt):
            return FilterResult(
                False,
                "Prompt contains a potentially unsafe instruction."
            )

    return FilterResult(True, "Prompt passed basic checks.")