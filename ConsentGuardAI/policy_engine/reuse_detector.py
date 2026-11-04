"""Detect reuse of previously stored user data, handling encrypted records and paraphrases."""

import re
from dataclasses import dataclass
from typing import Optional, List, Set, Tuple

from security.encryption import decrypt_data, EncryptionError


@dataclass(frozen=True)
class ReuseMatch:
    """Result of data reuse detection."""

    detected: bool
    record_id: Optional[int] = None
    original_purpose: Optional[str] = None
    match_type: Optional[str] = None  # "exact", "partial", "paraphrase", "decryption_error"
    reason: str = "No previously stored data reuse detected."
    matched_snippet: Optional[str] = None
    data_classification: Optional[str] = None
    decryption_failed: bool = False


class DataReuseDetector:
    """Compare a new prompt with previously stored user-owned records (Objective 3)."""

    STOP_WORDS: Set[str] = {
        "the", "and", "a", "an", "is", "in", "it", "of", "to", "for", "with",
        "on", "at", "by", "this", "that", "from", "as", "was", "are", "be",
        "has", "had", "have", "we", "they", "he", "she", "i", "you", "use",
        "please", "our", "their", "about", "can", "will", "do", "did", "does",
        "or", "so", "if", "but", "not", "what", "how", "when", "where", "which",
        "into", "over", "after", "before", "than", "more", "some", "any", "all",
        "give", "each", "three", "two", "one", "ways", "way",
    }

    # Canonical synonyms for enterprise data and common organizational concepts
    SYNONYM_MAP = {
        "staff": "employe",
        "worker": "employe",
        "workers": "employe",
        "workforce": "employe",
        "personnel": "employe",
        "team": "employe",
        "coaching": "train",
        "workshop": "train",
        "seminar": "train",
        "instruction": "train",
        "onboarding": "train",
        "timetable": "schedul",
        "calendar": "schedul",
        "timeline": "schedul",
        "agenda": "schedul",
        "inquiry": "investig",
        "probe": "investig",
        "hearing": "investig",
        "audit": "investig",
        "statement": "witnes",
        "deposition": "witnes",
        "testimony": "witnes",
        "commercial": "advertis",
        "campaign": "advertis",
        "promotion": "advertis",
        "advertisement": "advertis",
        "advertising": "advertis",
        "announcement": "announc",
    }

    @classmethod
    def stem(cls, word: str) -> str:
        """Normalize word by canonicalizing synonyms and stripping common English suffixes."""
        w = word.lower()
        if w in cls.SYNONYM_MAP:
            return cls.SYNONYM_MAP[w]

        for suffix in ("ation", "ement", "ment", "ings", "ing", "ized", "ised", "ies", "ied", "ed", "es", "s"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 4:
                w = w[:-len(suffix)]
                break

        return cls.SYNONYM_MAP.get(w, w)

    @classmethod
    def normalize(cls, text: str) -> str:
        """Normalize text by folding case and stripping punctuation."""
        if not isinstance(text, str):
            return ""
        return " ".join(re.findall(r"\w+", text.casefold()))

    @classmethod
    def get_stemmed_tokens(cls, text: str) -> List[str]:
        """Extract stemmed content tokens excluding stop words."""
        norm = cls.normalize(text)
        return [cls.stem(w) for w in norm.split() if w not in cls.STOP_WORDS and len(w) >= 2]

    def _extract_clauses(self, text: str, min_words: int = 3) -> List[str]:
        """Extract multi-word clauses or sentences for partial matching."""
        raw_parts = re.split(r"[.\n;!?:]+", text)
        clauses = []
        for part in raw_parts:
            norm = self.normalize(part)
            words = norm.split()
            if len(words) >= min_words:
                clauses.append(norm)
        return clauses

    def _get_ngrams(self, words: List[str], n: int = 2) -> Set[str]:
        """Extract n-grams of words."""
        if len(words) < n:
            return set()
        return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}

    def detect_in_records(self, prompt: str, records: list) -> ReuseMatch:
        """Compare a prompt against a user's stored records, decrypting securely.

        Ensures that encrypted records are decrypted through the trusted layer
        and that checks are NEVER silently skipped due to encryption or decryption failure.
        Detects exact matches, clauses, key phrases, token overlap, and paraphrases while
        preventing false matches on unrelated conceptual queries.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        normalized_prompt = self.normalize(prompt)
        prompt_stemmed_tokens = self.get_stemmed_tokens(prompt)
        prompt_stemmed_set = set(prompt_stemmed_tokens)
        prompt_2grams = self._get_ngrams(prompt_stemmed_tokens, n=2)
        prompt_3grams = self._get_ngrams(prompt_stemmed_tokens, n=3)

        candidates: List[Tuple[float, ReuseMatch]] = []

        for record in records:
            record_id = getattr(record, "id", None)
            orig_purpose = getattr(record, "original_purpose", None)
            classification = getattr(record, "data_classification", "Confidential")
            previous_text = None

            # 1. Trusted decryption of stored encrypted records
            encrypted_data = getattr(record, "data_encrypted", None)
            if encrypted_data is not None:
                try:
                    if isinstance(encrypted_data, bytes):
                        ciphertext = encrypted_data.decode("utf-8")
                    else:
                        ciphertext = str(encrypted_data)
                    previous_text = decrypt_data(ciphertext)
                except EncryptionError as err:
                    # Fail-closed: do not allow check to proceed
                    return ReuseMatch(
                        detected=True,
                        record_id=record_id,
                        original_purpose=orig_purpose,
                        match_type="decryption_error",
                        reason=(
                            f"Decryption failed for stored record #{record_id}. "
                            "Reuse check cannot safely complete; request blocked."
                        ),
                        data_classification=classification,
                        decryption_failed=True,
                    )
                except Exception as err:
                    return ReuseMatch(
                        detected=True,
                        record_id=record_id,
                        original_purpose=orig_purpose,
                        match_type="decryption_error",
                        reason=f"Error decrypting record #{record_id}: {err}",
                        data_classification=classification,
                        decryption_failed=True,
                    )

            # Fallback to plain content attribute if present (e.g. test mocks)
            if previous_text is None:
                previous_text = getattr(record, "content", None)

            if not isinstance(previous_text, str) or not previous_text.strip():
                continue

            normalized_previous = self.normalize(previous_text)
            if not normalized_previous:
                continue

            # Record metadata to support holistic asset matching
            rec_title = getattr(record, "title", "") or ""
            rec_desc = getattr(record, "description", "") or ""
            full_record_text = f"{rec_title} {rec_desc} {previous_text}"
            record_stemmed_tokens = self.get_stemmed_tokens(full_record_text)
            record_stemmed_set = set(record_stemmed_tokens)

            # 2. Exact match check
            if normalized_previous in normalized_prompt or (
                len(normalized_prompt) >= 20 and normalized_prompt in normalized_previous
            ):
                candidates.append((
                    100.0,
                    ReuseMatch(
                        detected=True,
                        record_id=record_id,
                        original_purpose=orig_purpose,
                        match_type="exact",
                        reason="Previously stored confidential data appears directly in the prompt.",
                        matched_snippet=previous_text[:120],
                        data_classification=classification,
                    )
                ))
                continue

            # 3. Partial match check via clause matching
            clauses = self._extract_clauses(previous_text, min_words=3)
            clause_matched = False
            for clause in clauses:
                if clause in normalized_prompt:
                    candidates.append((
                        85.0,
                        ReuseMatch(
                            detected=True,
                            record_id=record_id,
                            original_purpose=orig_purpose,
                            match_type="partial",
                            reason="Significant confidential clauses from a previously stored record were detected in the prompt.",
                            matched_snippet=clause[:120],
                            data_classification=classification,
                        )
                    ))
                    clause_matched = True
                    break

            if clause_matched:
                continue

            # 4. Multi-token phrase matching (3-grams)
            record_3grams = self._get_ngrams(record_stemmed_tokens, n=3)
            matching_3grams = prompt_3grams & record_3grams
            if matching_3grams:
                matched_phrase = next(iter(matching_3grams))
                candidates.append((
                    75.0,
                    ReuseMatch(
                        detected=True,
                        record_id=record_id,
                        original_purpose=orig_purpose,
                        match_type="partial",
                        reason=f"Confidential key phrase '{matched_phrase}' from record #{record_id} was detected in the prompt.",
                        matched_snippet=matched_phrase,
                        data_classification=classification,
                    )
                ))
                continue

            # 5. Token overlap and 2-gram evaluation
            record_2grams = self._get_ngrams(record_stemmed_tokens, n=2)
            matching_2grams = prompt_2grams & record_2grams

            if record_stemmed_set and prompt_stemmed_set:
                intersection = prompt_stemmed_set & record_stemmed_set
                prompt_overlap = len(intersection) / len(prompt_stemmed_set)
                record_overlap = len(intersection) / len(record_stemmed_set)

                # Two or more matching 2-grams (e.g. "employee training" + "training schedule")
                if len(matching_2grams) >= 2 and len(intersection) >= 3:
                    matched_phrases = ", ".join(list(matching_2grams)[:2])
                    candidates.append((
                        70.0 + (len(matching_2grams) * 5),
                        ReuseMatch(
                            detected=True,
                            record_id=record_id,
                            original_purpose=orig_purpose,
                            match_type="partial",
                            reason=f"Key protected phrases '{matched_phrases}' from record #{record_id} were detected in the prompt.",
                            matched_snippet=", ".join(list(intersection)[:6]),
                            data_classification=classification,
                        )
                    ))
                    continue

                # Single 2-gram with substantial prompt coverage (>= 30% of prompt references record)
                if len(matching_2grams) >= 1 and (prompt_overlap >= 0.30 or record_overlap >= 0.25) and len(intersection) >= 2:
                    matched_phrase = next(iter(matching_2grams))
                    candidates.append((
                        60.0 + (prompt_overlap * 20),
                        ReuseMatch(
                            detected=True,
                            record_id=record_id,
                            original_purpose=orig_purpose,
                            match_type="partial",
                            reason=f"Key protected phrase '{matched_phrase}' from record #{record_id} was detected in the prompt.",
                            matched_snippet=", ".join(list(intersection)[:6]),
                            data_classification=classification,
                        )
                    ))
                    continue

                # Substantial keyword overlap / paraphrase check:
                # Requires at least 3 matching content terms AND >= 35% prompt coverage or >= 25% record coverage
                if len(intersection) >= 3 and (prompt_overlap >= 0.35 or record_overlap >= 0.25):
                    overlap_score = 45.0 + (prompt_overlap * 40.0) + (len(intersection) * 5)
                    candidates.append((
                        overlap_score,
                        ReuseMatch(
                            detected=True,
                            record_id=record_id,
                            original_purpose=orig_purpose,
                            match_type="partial",
                            reason=(
                                f"Significant confidential content overlap detected with record #{record_id} "
                                f"({int(prompt_overlap * 100)}% of prompt references tracked data)."
                            ),
                            matched_snippet=", ".join(list(intersection)[:6]),
                            data_classification=classification,
                        )
                    ))

        # Select the candidate with highest match confidence score
        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)
            best_score, best_match = candidates[0]
            if best_score >= 45.0:
                return best_match

        return ReuseMatch(detected=False)
