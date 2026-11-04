"""Purpose-based data-use validation for ConsentGuardAI."""

from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import re

logger = logging.getLogger(__name__)
SIMILARITY_THRESHOLD = 0.80


@dataclass(frozen=True)
class PurposeCheck:
    allowed: bool
    requested_purpose: str
    consented_purpose: str
    reason: str
    similarity: float | None = None


class PurposeEngine:
    """Compare purposes; similarity alone never grants authorization."""

    @staticmethod
    def normalize(purpose: str) -> str:
        if not isinstance(purpose, str):
            return ""
        return " ".join(re.findall(r"\w+", purpose.casefold()))

    @staticmethod
    def _lexical_similarity(s1: str, s2: str) -> float:
        """Compute token-based Jaccard similarity for resilient offline comparison."""
        words1 = set(s1.split())
        words2 = set(s2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def check_purpose(
        self,
        requested_purpose: str,
        consented_purpose: str,
    ) -> PurposeCheck:
        requested = self.normalize(requested_purpose)
        consented = self.normalize(consented_purpose)

        if not requested or not consented:
            return PurposeCheck(
                allowed=False,
                requested_purpose=requested_purpose if isinstance(requested_purpose, str) else "",
                consented_purpose=consented_purpose if isinstance(consented_purpose, str) else "",
                reason="Purpose is missing or invalid; access denied.",
                similarity=0.0,
            )

        if requested == consented:
            return PurposeCheck(
                allowed=True,
                requested_purpose=requested_purpose,
                consented_purpose=consented_purpose,
                reason="Purpose exactly matches the authorized purpose.",
                similarity=1.0,
            )

        # Compute similarity using lexical comparison as primary fast baseline
        similarity = self._lexical_similarity(requested, consented)

        # Optional: Check if embedding model is enabled and cached
        if os.getenv("CONSENTGUARD_ENABLE_EMBEDDINGS", "false").lower() == "true":
            try:
                from sentence_transformers import SentenceTransformer
                model_name = os.getenv(
                    "CONSENTGUARD_EMBEDDING_MODEL",
                    "sentence-transformers/all-MiniLM-L6-v2",
                )
                model = SentenceTransformer(model_name)
                embeddings = model.encode(
                    [requested, consented],
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
                similarity = float(embeddings[0] @ embeddings[1])
            except Exception:
                logger.warning("Embedding model unavailable; using lexical similarity")

        if similarity >= SIMILARITY_THRESHOLD:
            reason = (
                "Purpose is semantically similar, but explicit policy authorization "
                "for the requested purpose is required."
            )
        else:
            reason = (
                "Requested purpose differs from the original authorized purpose; "
                "authorization is denied."
            )

        # Similarity score is evidence for review, not automatic permission
        return PurposeCheck(
            allowed=False,
            requested_purpose=requested_purpose,
            consented_purpose=consented_purpose,
            reason=reason,
            similarity=round(similarity, 3),
        )
