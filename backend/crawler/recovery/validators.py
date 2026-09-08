from __future__ import annotations

import re
from typing import Any


class RecoveryValidator:
    """
    Validates the output of a recovery transformation.

    Detection answers:
        "Could this be Base64?"

    Validation answers:
        "Did decoding it actually produce plausible content?"

    This validator is deterministic and does not use an LLM.
    """

    MIN_TEXT_LENGTH = 2

    URL_RE = re.compile(
        r"https?://[^\s<>'\"]+",
        re.IGNORECASE,
    )

    EMAIL_RE = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )

    DOMAIN_RE = re.compile(
        r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b"
    )

    COMMON_WORDS = {
        "a",
        "about",
        "address",
        "and",
        "are",
        "bitcoin",
        "buyer",
        "buy",
        "cocaine",
        "contact",
        "crypto",
        "drugs",
        "email",
        "for",
        "from",
        "hello",
        "heroin",
        "is",
        "listing",
        "market",
        "marijuana",
        "medicine",
        "message",
        "of",
        "on",
        "or",
        "payment",
        "price",
        "seller",
        "signal",
        "telegram",
        "that",
        "the",
        "this",
        "to",
        "wallet",
        "with",
        "world",
        "you",
    }

    @classmethod
    def validate(
        cls,
        transformation: str,
        original: str,
        result: Any,
    ) -> tuple[bool, float, str]:
        """
        Returns:

            is_valid
            confidence
            reason
        """

        if result is None:
            return False, 0.0, "Transformation produced no result."

        if isinstance(result, bytes):
            if not result:
                return False, 0.0, "Transformation produced empty bytes."

            return cls._validate_bytes(
                transformation,
                original,
                result,
            )

        if not isinstance(result, str):
            return (
                False,
                0.0,
                f"Unsupported result type: {type(result).__name__}.",
            )

        return cls._validate_text(
            transformation,
            original,
            result.strip(),
        )

    # ------------------------------------------------------------------
    # Bytes
    # ------------------------------------------------------------------

    @classmethod
    def _validate_bytes(
        cls,
        transformation: str,
        original: str,
        result: bytes,
    ) -> tuple[bool, float, str]:

        signature = cls._detect_file_signature(result)

        if signature:
            return (
                True,
                0.96,
                f"Recovered bytes match known file signature: {signature}.",
            )

        try:
            text = result.decode("utf-8")
        except UnicodeDecodeError:
            return (
                False,
                0.15,
                "Recovered bytes are neither valid UTF-8 nor a recognized file.",
            )

        return cls._validate_text(
            transformation,
            original,
            text.strip(),
        )

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    @classmethod
    def _validate_text(
        cls,
        transformation: str,
        original: str,
        result: str,
    ) -> tuple[bool, float, str]:

        if len(result) < cls.MIN_TEXT_LENGTH:
            return (
                False,
                0.10,
                "Recovered text is too short.",
            )

        printable_ratio = cls._printable_ratio(result)

        if printable_ratio < 0.85:
            return (
                False,
                0.15,
                "Recovered text contains too many non-printable characters.",
            )

        words = cls._extract_words(result)

        score = 0.50
        reasons: list[str] = []

        # --------------------------------------------------------------
        # Strong structural signals
        # --------------------------------------------------------------

        if cls.URL_RE.search(result):
            score += 0.25
            reasons.append("contains a URL")

        if cls.EMAIL_RE.search(result):
            score += 0.20
            reasons.append("contains an email address")

        if cls.DOMAIN_RE.search(result):
            score += 0.10
            reasons.append("contains a domain-like value")

        stripped = result.strip()

        if (
            (stripped.startswith("{") and stripped.endswith("}"))
            or
            (stripped.startswith("[") and stripped.endswith("]"))
        ):
            score += 0.15
            reasons.append("looks like structured JSON")

        if "-----BEGIN PGP " in result:
            score += 0.20
            reasons.append("contains an OpenPGP marker")

        # --------------------------------------------------------------
        # Natural language signals
        # --------------------------------------------------------------

        if len(words) >= 2:
            score += 0.10
            reasons.append("contains multiple word-like tokens")

        dictionary_score = cls._common_word_score(words)

        if dictionary_score > 0:
            score += min(dictionary_score * 0.30, 0.30)
            reasons.append("contains recognizable common words")

        # --------------------------------------------------------------
        # Noise penalty
        # --------------------------------------------------------------

        if cls._looks_like_noise(result):
            score -= 0.30
            reasons.append("appears highly repetitive or noisy")

        # --------------------------------------------------------------
        # Transformation-specific bonus
        # --------------------------------------------------------------

        if transformation in {
            "base64",
            "base32",
            "hex",
            "url_encoding",
        }:
            score += 0.10
            reasons.append(
                "decoder produced structurally valid text"
            )

        # Caesar/ROT13 need more semantic evidence.
        elif transformation in {
            "rot13",
            "caesar",
        }:
            if dictionary_score < 0.10:
                score -= 0.10

        score = max(0.0, min(score, 0.99))

        if score >= 0.70:
            return (
                True,
                score,
                (
                    "Recovered content passed validation"
                    + (
                        f": {', '.join(reasons)}."
                        if reasons
                        else "."
                    )
                ),
            )

        return (
            False,
            score,
            (
                "Recovered content did not reach validation threshold"
                + (
                    f": {', '.join(reasons)}."
                    if reasons
                    else "."
                )
            ),
        )

    # ------------------------------------------------------------------
    # Text heuristics
    # ------------------------------------------------------------------

    @staticmethod
    def _printable_ratio(text: str) -> float:
        if not text:
            return 0.0

        printable = sum(
            1
            for char in text
            if char.isprintable()
            or char in "\n\r\t"
        )

        return printable / len(text)

    @staticmethod
    def _extract_words(text: str) -> list[str]:
        return re.findall(
            r"\b[a-zA-Z]{2,}\b",
            text.lower(),
        )

    @classmethod
    def _common_word_score(
        cls,
        words: list[str],
    ) -> float:
        if not words:
            return 0.0

        matches = sum(
            1
            for word in words
            if word in cls.COMMON_WORDS
        )

        return matches / len(words)

    @staticmethod
    def _looks_like_noise(text: str) -> bool:
        if len(text) < 8:
            return False

        unique_chars = len(set(text))

        if unique_chars <= 3:
            return True

        most_common_ratio = max(
            text.count(char)
            for char in set(text)
        ) / len(text)

        return most_common_ratio >= 0.75

    # ------------------------------------------------------------------
    # Magic-byte detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_file_signature(
        data: bytes,
    ) -> str | None:

        signatures = {
            b"%PDF-": "PDF",
            b"\x89PNG\r\n\x1a\n": "PNG",
            b"\xff\xd8\xff": "JPEG",
            b"GIF87a": "GIF",
            b"GIF89a": "GIF",
            b"PK\x03\x04": "ZIP/container",
            b"\x1f\x8b": "GZIP",
        }

        for magic, name in signatures.items():
            if data.startswith(magic):
                return name

        return None