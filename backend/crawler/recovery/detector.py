import base64
import binascii
import re
from dataclasses import dataclass
from typing import List


@dataclass
class DetectionCandidate:
    """
    Represents a possible transformation detected in content.
    """
    transformation: str
    confidence: float
    reason: str


class RecoveryDetector:
    """
    Deterministic detector for common encoded, obfuscated,
    and encrypted content.

    This class ONLY detects likely transformations.
    It does not modify or decode the content.
    """

    # Base64 characters, allowing normal whitespace inside the payload.
    BASE64_RE = re.compile(
        r"^[A-Za-z0-9+/]+={0,2}$"
    )

    # Hexadecimal string.
    HEX_RE = re.compile(
        r"^(?:[0-9a-fA-F]{2})+$"
    )

    # Base32 alphabet.
    BASE32_RE = re.compile(
        r"^[A-Z2-7]+=*$",
        re.IGNORECASE,
    )

    # URL percent encoding.
    URL_ENCODING_RE = re.compile(
        r"%(?:[0-9A-Fa-f]{2})"
    )

    @classmethod
    def detect(cls, text: str | None) -> List[DetectionCandidate]:
        """
        Returns possible transformations ordered by confidence.

        The detector does not assume that the first matching rule
        is correct. Multiple candidates can be returned and later
        validated by the recovery engine.
        """
        if not text:
            return []

        candidates: List[DetectionCandidate] = []

        normalized = cls._normalize_candidate(text)

        if not normalized:
            return []

        # Strong format/signature detection first.
        pgp_candidate = cls._detect_pgp(normalized)
        if pgp_candidate:
            candidates.append(pgp_candidate)

        url_candidate = cls._detect_url_encoding(normalized)
        if url_candidate:
            candidates.append(url_candidate)

        hex_candidate = cls._detect_hex(normalized)
        if hex_candidate:
            candidates.append(hex_candidate)

        base64_candidate = cls._detect_base64(normalized)
        if base64_candidate:
            candidates.append(base64_candidate)

        base32_candidate = cls._detect_base32(normalized)
        if base32_candidate:
            candidates.append(base32_candidate)

        # Obfuscation has weaker signatures, so it receives lower
        # initial confidence and must be validated later.
        rot13_candidate = cls._detect_rot13_candidate(normalized)
        if rot13_candidate:
            candidates.append(rot13_candidate)

        caesar_candidate = cls._detect_caesar_candidate(normalized)
        if caesar_candidate:
            candidates.append(caesar_candidate)

        candidates.sort(
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )

        return candidates

    @staticmethod
    def _normalize_candidate(text: str) -> str:
        """
        Normalize whitespace while preserving word boundaries.

        This is intentionally NOT HTML cleaning and does not modify
        the original evidence.
        """
        return " ".join(text.split())

    @staticmethod
    def _detect_pgp(text: str) -> DetectionCandidate | None:
        """
        Detect common ASCII-armored OpenPGP blocks.
        """
        if (
            "-----BEGIN PGP MESSAGE-----" in text
            or "-----BEGIN PGP SIGNED MESSAGE-----" in text
            or "-----BEGIN PGP PUBLIC KEY BLOCK-----" in text
            or "-----BEGIN PGP PRIVATE KEY BLOCK-----" in text
        ):
            return DetectionCandidate(
                transformation="pgp",
                confidence=0.99,
                reason="Recognized OpenPGP ASCII armor marker.",
            )

        return None

    @staticmethod
    def _detect_url_encoding(text: str) -> DetectionCandidate | None:
        matches = RecoveryDetector.URL_ENCODING_RE.findall(text)

        if not matches:
            return None

        # A single %XX occurrence is weak evidence.
        # Multiple occurrences are much stronger.
        confidence = min(
            0.60 + (len(matches) * 0.05),
            0.95,
        )

        return DetectionCandidate(
            transformation="url_encoding",
            confidence=confidence,
            reason=f"Detected {len(matches)} percent-encoded byte sequence(s).",
        )

    @staticmethod
    def _detect_hex(text: str) -> DetectionCandidate | None:
        if len(text) < 8:
            return None

        if len(text) % 2 != 0:
            return None

        if not RecoveryDetector.HEX_RE.fullmatch(text):
            return None

        return DetectionCandidate(
            transformation="hex",
            confidence=0.88,
            reason="Content consists entirely of hexadecimal byte pairs.",
        )

    @staticmethod
    def _detect_base64(text: str) -> DetectionCandidate | None:
        if len(text) < 12:
            return None

        # Base64 length must be divisible by 4.
        if len(text) % 4 != 0:
            return None

        if not RecoveryDetector.BASE64_RE.fullmatch(text):
            return None

        try:
            decoded = base64.b64decode(
                text,
                validate=True,
            )
        except (ValueError, binascii.Error):
            return None

        if not decoded:
            return None

        # Require at least some meaningful output.
        printable = sum(
            1
            for byte in decoded
            if 32 <= byte <= 126
            or byte in (9, 10, 13)
        )

        printable_ratio = printable / len(decoded)

        if printable_ratio >= 0.85:
            confidence = 0.94
            reason = (
                "Valid Base64 structure and decoded output is "
                "predominantly printable."
            )
        elif printable_ratio >= 0.60:
            confidence = 0.78
            reason = (
                "Valid Base64 structure with partially printable "
                "decoded output."
            )
        else:
            confidence = 0.55
            reason = (
                "Valid Base64 structure, but decoded output "
                "appears mostly binary."
            )

        return DetectionCandidate(
            transformation="base64",
            confidence=confidence,
            reason=reason,
        )

    @staticmethod
    def _detect_base32(text: str) -> DetectionCandidate | None:
        if len(text) < 16:
            return None

        if not RecoveryDetector.BASE32_RE.fullmatch(text):
            return None

        try:
            decoded = base64.b32decode(
                text,
                casefold=True,
            )
        except (ValueError, binascii.Error):
            return None

        if not decoded:
            return None

        printable = sum(
            1
            for byte in decoded
            if 32 <= byte <= 126
            or byte in (9, 10, 13)
        )

        printable_ratio = printable / len(decoded)

        if printable_ratio >= 0.85:
            confidence = 0.90
        elif printable_ratio >= 0.60:
            confidence = 0.72
        else:
            confidence = 0.50

        return DetectionCandidate(
            transformation="base32",
            confidence=confidence,
            reason=(
                "Valid Base32 structure and successfully decoded "
                "the candidate payload."
            ),
        )

    @staticmethod
    def _detect_rot13_candidate(text: str) -> DetectionCandidate | None:
        """
        ROT13 has no reliable structural signature.

        Therefore this is deliberately a weak candidate. The actual
        decoded result must be scored by the validator.
        """
        if len(text) < 8:
            return None

        alpha_chars = sum(char.isalpha() for char in text)

        if alpha_chars / len(text) < 0.50:
            return None

        return DetectionCandidate(
            transformation="rot13",
            confidence=0.30,
            reason=(
                "Alphabetic-heavy content could potentially represent "
                "ROT13-obfuscated text; requires validation."
            ),
        )

    @staticmethod
    def _detect_caesar_candidate(text: str) -> DetectionCandidate | None:
        """
        Caesar cipher also has no dependable signature.

        We only flag it as a low-confidence possibility here.
        The validator will test individual shifts and determine
        whether any result is plausible.
        """
        if len(text) < 12:
            return None

        alpha_chars = sum(char.isalpha() for char in text)

        if alpha_chars / len(text) < 0.60:
            return None

        return DetectionCandidate(
            transformation="caesar",
            confidence=0.25,
            reason=(
                "Alphabetic-heavy content could potentially be Caesar-"
                "shifted text; requires shift testing and validation."
            ),
        )