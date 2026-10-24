
"""Purpose-based data-use validation for ConsentGuardAI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PurposeCheck:
    allowed: bool
    requested_purpose: str
    consented_purpose: str
    reason: str


class PurposeEngine:
    """Check whether requested data use matches the consented purpose."""

    @staticmethod
    def normalize(purpose: str) -> str:
        if not isinstance(purpose, str):
            return ""
        return " ".join(purpose.casefold().split())

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
                requested_purpose or "",
                consented_purpose or "",
                "Purpose is missing or invalid; access denied.",
            )

        if requested != consented:
            return PurposeCheck(
                False,
                requested_purpose,
                consented_purpose,
                "Requested purpose does not match the consented purpose.",
            )

        return PurposeCheck(
            True,
            requested_purpose,
            consented_purpose,
            "Requested purpose matches the consented purpose.",
        )
