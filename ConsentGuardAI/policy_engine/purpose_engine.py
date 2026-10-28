
"""Purpose-based data-use validation for ConsentGuardAI."""

from dataclasses import dataclass
from functools import lru_cache
import logging
import os

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
        return " ".join(purpose.casefold().split())

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_model():
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

        if requested == consented:
            return PurposeCheck(
                True,
                requested_purpose,
                consented_purpose,
                "Purpose exactly matches the consented purpose.",
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
            logger.exception("Purpose similarity model failed")
            return PurposeCheck(
                False,
                requested_purpose,
                consented_purpose,
                "Purpose similarity could not be verified; access denied.",
            )

        if similarity >= SIMILARITY_THRESHOLD:
            reason = (
                "Purpose is semantically similar, but explicit consent "
                "for the requested purpose is required."
            )
        else:
            reason = (
                "Requested purpose differs from the consented purpose; "
                "authorization is denied."
            )

        # A similarity score is evidence for review, not permission.
        return PurposeCheck(
            False,
            requested_purpose,
            consented_purpose,
            reason,
            similarity,
        )
