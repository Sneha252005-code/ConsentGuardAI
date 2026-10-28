
"""Purpose-based data-use validation for ConsentGuardAI."""

from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import re

logger = logging.getLogger(__name__)

# Conservative threshold; validate it against your project test data.
SIMILARITY_THRESHOLD = 0.80


@dataclass(frozen=True)
class PurposeCheck:
    allowed: bool
    requested_purpose: str
    consented_purpose: str
    reason: str
    similarity: float | None = None


class PurposeEngine:
    """Compare requested and consented purposes using semantic similarity."""

    @staticmethod
    def normalize(purpose: str) -> str:
        if not isinstance(purpose, str):
            return ""
        return " ".join(purpose.casefold().split())

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_model():
        # Lazy loading avoids loading the NLP model unless needed.
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv(
            "CONSENTGUARD_EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        return SentenceTransformer(model_name)

    def check_purpose(
        self,
        requested_purpose: str,
        consented_purpose: str,
    ) -> PurposeCheck:
        requested = self.normalize(requested_purpose)
        consented = self.normalize(consented_purpose)

        if not requested or not consented:
            return PurposeCheck(
                False,
                requested_purpose if isinstance(requested_purpose, str) else "",
                consented_purpose if isinstance(consented_purpose, str) else "",
                "Purpose is missing or invalid; access denied.",
            )

        # Exact matches are safe to recognize without loading an NLP model.
        if requested == consented:
            return PurposeCheck(
                True,
                requested_purpose,
                consented_purpose,
                "Requested purpose exactly matches the consented purpose.",
                1.0,
            )

        try:
            model = self._load_model()
            embeddings = model.encode(
                [requested, consented],
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            similarity = float(embeddings[0] @ embeddings[1])
        except Exception:
            # Fail closed: model errors must never grant authorization.
            logger.exception("Purpose similarity model failed")
            return PurposeCheck(
                False,
                requested_purpose,
                consented_purpose,
                "Purpose similarity could not be verified; access denied.",
            )

        if similarity >= SIMILARITY_THRESHOLD:
            return PurposeCheck(
                True,
                requested_purpose,
                consented_purpose,
                "Purpose similarity meets the configured threshold; consent and category checks are still required.",
                similarity,
            )

        return PurposeCheck(
            False,
            requested_purpose,
            consented_purpose,
            "Requested purpose differs from the consented purpose; additional authorization is required.",
            similarity,
        )
