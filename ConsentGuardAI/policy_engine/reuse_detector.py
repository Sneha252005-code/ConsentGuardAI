
"""Detect direct reuse of previously stored user data."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ReuseMatch:
    detected: bool
    record_id: int | None = None
    original_purpose: str | None = None
    match_type: str | None = None
    reason: str = "No previously stored data reuse detected."


class DataReuseDetector:
    """Compare a new prompt with previously retrieved user-owned records."""

    @staticmethod
    def normalize(text: str) -> str:
        return " ".join(re.findall(r"\w+", text.casefold()))

    def detect_in_records(self, prompt: str, records: list) -> ReuseMatch:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        normalized_prompt = self.normalize(prompt)

        for record in records:
            previous_text = getattr(record, "content", None)

            # Only compare plaintext supplied by the trusted storage layer.
            if not isinstance(previous_text, str) or not previous_text.strip():
                continue

            normalized_previous = self.normalize(previous_text)

            if (
                normalized_previous
                and normalized_previous in normalized_prompt
            ):
                return ReuseMatch(
                    detected=True,
                    record_id=getattr(record, "id", None),
                    original_purpose=getattr(
                        record, "original_purpose", None
                    ),
                    match_type="exact",
                    reason="Previously stored data appears in the new prompt.",
                )

        return ReuseMatch(detected=False)
