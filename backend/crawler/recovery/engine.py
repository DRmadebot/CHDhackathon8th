from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from crawler.recovery.detector import (
    DetectionCandidate,
    RecoveryDetector,
)
from crawler.recovery.decoders import RecoveryDecoders
from crawler.recovery.encryption import EncryptionHandler
from crawler.recovery.validators import RecoveryValidator


@dataclass
class RecoveryStep:
    """
    Represents one successful recovery transformation.
    """

    transformation: str
    confidence: float
    reason: str
    input_preview: str
    output_preview: str


@dataclass
class RecoveryResult:
    """
    Complete result of the content recovery process.

    original_content:
        Exact original artifact supplied to the engine.

    recovered_content:
        Derived content after successful recovery.
    """

    status: str
    original_content: str
    recovered_content: str
    recovered: bool
    confidence: float
    transformations: list[dict[str, Any]]
    candidates_considered: list[dict[str, Any]]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the result to a dictionary suitable for JSON storage.
        """
        return asdict(self)


class RecoveryEngine:
    """
    Deterministic content recovery engine.

    Pipeline:

        raw artifact
            ↓
        temporary analysis representation
            ↓
        encryption-format detection
            ↓
        transformation detection
            ↓
        decoding / de-obfuscation
            ↓
        validation
            ↓
        optional nested transformation
            ↓
        recovered content

    Supported transformations:

        - Base64
        - Base32
        - Hex
        - URL encoding
        - ROT13
        - Caesar
        - PGP format detection

    Important:

        - No LLM is used.
        - Original content is never modified.
        - Cryptographic encryption is not brute-forced.
        - Recovery is bounded to prevent runaway processing.
    """

    # Maximum number of nested transformations.
    MAX_TRANSFORMATION_DEPTH = 3

    # Maximum size of artifact analyzed by this layer.
    MAX_INPUT_LENGTH = 500_000

    # Minimum confidence required after validation.
    MIN_CONFIDENCE_TO_APPLY = 0.60

    # Prevent excessive processing of embedded payloads.
    MAX_EMBEDDED_PAYLOADS = 100

    # ------------------------------------------------------------------
    # Embedded payload patterns
    # ------------------------------------------------------------------

    BASE64_FRAGMENT_RE = re.compile(
        r"(?<![A-Za-z0-9+/])"
        r"[A-Za-z0-9+/]{12,}={0,2}"
        r"(?![A-Za-z0-9+/])"
    )

    HEX_FRAGMENT_RE = re.compile(
        r"(?<![0-9A-Fa-f])"
        r"(?:[0-9A-Fa-f]{2}){5,}"
        r"(?![0-9A-Fa-f])"
    )

    URL_FRAGMENT_RE = re.compile(
        r"(?:%[0-9A-Fa-f]{2}){2,}"
    )

    # ------------------------------------------------------------------
    # Main processing entry point
    # ------------------------------------------------------------------

    @classmethod
    def process(
        cls,
        raw_text: str | None,
    ) -> RecoveryResult:
        """
        Analyze and recover transformations from crawler content.
        """

        original = raw_text or ""

        # --------------------------------------------------------------
        # Empty input
        # --------------------------------------------------------------

        if not original:
            return RecoveryResult(
                status="no_content",
                original_content=original,
                recovered_content=original,
                recovered=False,
                confidence=0.0,
                transformations=[],
                candidates_considered=[],
            )

        # --------------------------------------------------------------
        # Size protection
        # --------------------------------------------------------------

        if len(original) > cls.MAX_INPUT_LENGTH:
            return RecoveryResult(
                status="skipped_too_large",
                original_content=original,
                recovered_content=original,
                recovered=False,
                confidence=0.0,
                transformations=[],
                candidates_considered=[],
                error=(
                    f"Input exceeds recovery size limit of "
                    f"{cls.MAX_INPUT_LENGTH} characters."
                ),
            )

        # --------------------------------------------------------------
        # Initialize result state BEFORE any detection.
        # --------------------------------------------------------------

        transformations: list[dict[str, Any]] = []
        candidates_considered: list[dict[str, Any]] = []

        # --------------------------------------------------------------
        # Create temporary analysis representation.
        #
        # The original artifact remains completely untouched.
        # --------------------------------------------------------------

        working_text = cls._build_analysis_text(
            original
        )

        if not working_text.strip():
            return RecoveryResult(
                status="no_analyzable_content",
                original_content=original,
                recovered_content=original,
                recovered=False,
                confidence=0.0,
                transformations=[],
                candidates_considered=[],
            )

        # --------------------------------------------------------------
        # Encryption detection
        # --------------------------------------------------------------

        encryption_detection = EncryptionHandler.detect(
            working_text
        )

        if encryption_detection.detected:
            candidates_considered.append(
                {
                    "transformation": (
                        encryption_detection.encryption_type
                    ),
                    "confidence": (
                        encryption_detection.confidence
                    ),
                    "reason": encryption_detection.reason,
                }
            )

            # At this stage we only recognize PGP.
            # Actual authorized decryption is a separate responsibility.
            if encryption_detection.encryption_type == "pgp":
                return RecoveryResult(
                    status="encrypted_key_required",
                    original_content=original,
                    recovered_content=working_text,
                    recovered=False,
                    confidence=encryption_detection.confidence,
                    transformations=[],
                    candidates_considered=candidates_considered,
                    error=(
                        "OpenPGP encrypted content detected. "
                        "Authorized private-key material is required "
                        "for decryption."
                    ),
                )

        # --------------------------------------------------------------
        # Current working representation
        # --------------------------------------------------------------

        current_text = working_text

        recovered_anything = False
        overall_confidence = 0.0

        # --------------------------------------------------------------
        # Transformation loop
        # --------------------------------------------------------------

        for _depth in range(
            cls.MAX_TRANSFORMATION_DEPTH
        ):
            candidates = RecoveryDetector.detect(
                current_text
            )

            # Search independently for encoded fragments embedded in
            # normal text/HTML.
            candidates.extend(
                cls._detect_embedded_payloads(
                    current_text
                )
            )

            candidates = cls._deduplicate_candidates(
                candidates
            )

            if not candidates:
                break

            candidates_considered.extend(
                candidate.__dict__
                for candidate in candidates
            )

            best_result = cls._try_candidates(
                current_text,
                candidates,
            )

            if best_result is None:
                break

            (
                transformed_text,
                candidate,
                validation_confidence,
                validation_reason,
            ) = best_result

            # Validation is the final gate.
            if (
                validation_confidence
                < cls.MIN_CONFIDENCE_TO_APPLY
            ):
                break

            if not transformed_text:
                break

            # Prevent endless no-op transformations.
            if transformed_text == current_text:
                break

            step_confidence = min(
                candidate.confidence,
                validation_confidence,
            )

            transformations.append(
                RecoveryStep(
                    transformation=(
                        candidate.transformation
                    ),
                    confidence=step_confidence,
                    reason=(
                        f"{candidate.reason} "
                        f"Validation: "
                        f"{validation_reason}"
                    ),
                    input_preview=cls._preview(
                        current_text
                    ),
                    output_preview=cls._preview(
                        transformed_text
                    ),
                ).__dict__
            )

            current_text = transformed_text
            recovered_anything = True

            if overall_confidence == 0.0:
                overall_confidence = step_confidence
            else:
                overall_confidence = min(
                    overall_confidence,
                    step_confidence,
                )

        # --------------------------------------------------------------
        # Successful recovery
        # --------------------------------------------------------------

        if recovered_anything:
            return RecoveryResult(
                status="recovered",
                original_content=original,
                recovered_content=current_text,
                recovered=True,
                confidence=overall_confidence,
                transformations=transformations,
                candidates_considered=candidates_considered,
            )

        # --------------------------------------------------------------
        # No successful recovery
        # --------------------------------------------------------------

        return RecoveryResult(
            status="unchanged",
            original_content=original,
            recovered_content=working_text,
            recovered=False,
            confidence=0.0,
            transformations=[],
            candidates_considered=candidates_considered,
        )

    # ------------------------------------------------------------------
    # Candidate execution
    # ------------------------------------------------------------------

    @classmethod
    def _try_candidates(
        cls,
        text: str,
        candidates: list[DetectionCandidate],
    ) -> (
        tuple[
            str,
            DetectionCandidate,
            float,
            str,
        ]
        | None
    ):
        """
        Try candidates from highest detection confidence to lowest.

        A candidate is accepted only if its output passes validation.
        """

        ordered = sorted(
            candidates,
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )

        for candidate in ordered:

            try:
                # ------------------------------------------------------
                # Base64
                # ------------------------------------------------------

                if candidate.transformation == "base64":
                    result = cls._recover_embedded(
                        text=text,
                        transformation="base64",
                        decoder=RecoveryDecoders.base64_decode,
                    )

                # ------------------------------------------------------
                # Base32
                # ------------------------------------------------------

                elif candidate.transformation == "base32":
                    result = cls._recover_embedded(
                        text=text,
                        transformation="base32",
                        decoder=RecoveryDecoders.base32_decode,
                    )

                # ------------------------------------------------------
                # Hex
                # ------------------------------------------------------

                elif candidate.transformation == "hex":
                    result = cls._recover_embedded(
                        text=text,
                        transformation="hex",
                        decoder=RecoveryDecoders.hex_decode,
                    )

                # ------------------------------------------------------
                # URL encoding
                # ------------------------------------------------------

                elif candidate.transformation == "url_encoding":
                    result = cls._recover_embedded(
                        text=text,
                        transformation="url_encoding",
                        decoder=RecoveryDecoders.url_decode,
                    )

                # ------------------------------------------------------
                # ROT13
                # ------------------------------------------------------

                elif candidate.transformation == "rot13":
                    result = RecoveryDecoders.rot13_decode(
                        text
                    )

                # ------------------------------------------------------
                # Caesar
                # ------------------------------------------------------

                elif candidate.transformation == "caesar":
                    result = cls._best_caesar_result(
                        text
                    )

                    if result is None:
                        continue

                # ------------------------------------------------------
                # PGP
                # ------------------------------------------------------

                elif candidate.transformation == "pgp":
                    # PGP detection is handled separately.
                    # No cryptographic operation occurs here.
                    continue

                else:
                    continue

                # ------------------------------------------------------
                # Caesar result
                # ------------------------------------------------------

                if isinstance(result, tuple):
                    transformed_text, candidate_shift = result

                    transformed_candidate = (
                        DetectionCandidate(
                            transformation=(
                                f"caesar_shift_"
                                f"{candidate_shift}"
                            ),
                            confidence=(
                                candidate.confidence
                            ),
                            reason=(
                                f"Caesar shift "
                                f"{candidate_shift} "
                                f"produced the strongest "
                                f"validated candidate."
                            ),
                        )
                    )

                    (
                        valid,
                        confidence,
                        reason,
                    ) = RecoveryValidator.validate(
                        "caesar",
                        text,
                        transformed_text,
                    )

                    if not valid:
                        continue

                    return (
                        transformed_text,
                        transformed_candidate,
                        confidence,
                        reason,
                    )

                # ------------------------------------------------------
                # Normal validation
                # ------------------------------------------------------

                (
                    valid,
                    confidence,
                    reason,
                ) = RecoveryValidator.validate(
                    candidate.transformation,
                    text,
                    result,
                )

                if not valid:
                    continue

                # ------------------------------------------------------
                # Binary → UTF-8 conversion
                # ------------------------------------------------------

                if isinstance(result, bytes):
                    try:
                        result = result.decode(
                            "utf-8"
                        )
                    except UnicodeDecodeError:
                        continue

                if not isinstance(result, str):
                    continue

                return (
                    result,
                    candidate,
                    confidence,
                    reason,
                )

            except (
                ValueError,
                TypeError,
                UnicodeError,
            ):
                # A bad candidate must never stop the crawler.
                continue

        return None

    # ------------------------------------------------------------------
    # Embedded payload recovery
    # ------------------------------------------------------------------

    @classmethod
    def _recover_embedded(
        cls,
        text: str,
        transformation: str,
        decoder: Callable[
            [str],
            str | bytes,
        ],
    ) -> str:
        """
        Recover transformation payloads embedded inside normal text.

        Example:

            Seller contact:
            SGVsbG8gV29ybGQ=

        becomes:

            Seller contact:
            Hello World
        """

        # --------------------------------------------------------------
        # Select payload pattern
        # --------------------------------------------------------------

        if transformation == "base64":
            pattern = cls.BASE64_FRAGMENT_RE

        elif transformation == "base32":
            pattern = re.compile(
                r"(?<![A-Z2-7])"
                r"[A-Z2-7]{16,}={0,6}"
                r"(?![A-Z2-7])",
                re.IGNORECASE,
            )

        elif transformation == "hex":
            pattern = cls.HEX_FRAGMENT_RE

        elif transformation == "url_encoding":
            pattern = cls.URL_FRAGMENT_RE

        else:
            return text

        matches = list(
            pattern.finditer(text)
        )

        matches = matches[
            :cls.MAX_EMBEDDED_PAYLOADS
        ]

        # --------------------------------------------------------------
        # Whole input is itself the candidate
        # --------------------------------------------------------------

        if not matches:
            result = decoder(text)

            if isinstance(result, bytes):
                try:
                    return result.decode(
                        "utf-8"
                    )
                except UnicodeDecodeError:
                    return result  # type: ignore[return-value]

            return result

        # --------------------------------------------------------------
        # Replace only matched fragments
        # --------------------------------------------------------------

        pieces: list[str] = []
        cursor = 0

        for match in matches:

            pieces.append(
                text[
                    cursor:match.start()
                ]
            )

            fragment = match.group(0)

            try:
                decoded = decoder(
                    fragment
                )

                if isinstance(decoded, bytes):
                    try:
                        decoded = decoded.decode(
                            "utf-8"
                        )
                    except UnicodeDecodeError:
                        # Leave binary payload unchanged.
                        decoded = fragment

                pieces.append(
                    str(decoded)
                )

            except (
                ValueError,
                TypeError,
                UnicodeError,
            ):
                # Failed candidate remains unchanged.
                pieces.append(
                    fragment
                )

            cursor = match.end()

        pieces.append(
            text[cursor:]
        )

        return "".join(pieces)

    # ------------------------------------------------------------------
    # Caesar
    # ------------------------------------------------------------------

    @classmethod
    def _best_caesar_result(
        cls,
        text: str,
    ) -> tuple[str, int] | None:
        """
        Test all Caesar shifts from 1-25 and select the strongest
        validated candidate.

        This is intentionally limited to Caesar's 26-value space.
        It is not cryptographic key brute-forcing.
        """

        best_text: str | None = None
        best_shift: int | None = None
        best_score = 0.0

        for shift in range(
            1,
            26,
        ):
            transformed = (
                RecoveryDecoders.caesar_decode(
                    text,
                    shift,
                )
            )

            (
                valid,
                confidence,
                _reason,
            ) = RecoveryValidator.validate(
                "caesar",
                text,
                transformed,
            )

            if (
                valid
                and confidence > best_score
            ):
                best_score = confidence
                best_text = transformed
                best_shift = shift

        if (
            best_text is None
            or best_shift is None
        ):
            return None

        return (
            best_text,
            best_shift,
        )

    # ------------------------------------------------------------------
    # Temporary analysis representation
    # ------------------------------------------------------------------

    @classmethod
    def _build_analysis_text(
        cls,
        raw_text: str,
    ) -> str:
        """
        Create a temporary representation for recovery detection.

        This is NOT the same as ContentCleaner.

        The raw artifact remains untouched.
        """

        # Remove HTML tags from the temporary copy so encoded payloads
        # can be detected as text fragments.

        text = re.sub(
            r"<[^>]+>",
            " ",
            raw_text,
        )

        # Normalize horizontal whitespace.

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        return text.strip()

    # ------------------------------------------------------------------
    # Embedded candidate detection
    # ------------------------------------------------------------------

    @classmethod
    def _detect_embedded_payloads(
        cls,
        text: str,
    ) -> list[DetectionCandidate]:
        """
        Detect encoded payloads inside otherwise normal text.

        Each candidate is actually tested against its decoder and
        validator before being reported.
        """

        candidates: list[
            DetectionCandidate
        ] = []

        # --------------------------------------------------------------
        # Base64
        # --------------------------------------------------------------

        base64_matches = list(
            cls.BASE64_FRAGMENT_RE.finditer(
                text
            )
        )

        for match in base64_matches[
            :cls.MAX_EMBEDDED_PAYLOADS
        ]:
            fragment = match.group(0)

            try:
                decoded = (
                    RecoveryDecoders.base64_decode(
                        fragment
                    )
                )

                (
                    valid,
                    _confidence,
                    _reason,
                ) = RecoveryValidator.validate(
                    "base64",
                    fragment,
                    decoded,
                )

                if valid:
                    candidates.append(
                        DetectionCandidate(
                            transformation="base64",
                            confidence=0.90,
                            reason=(
                                "Detected a valid Base64 payload "
                                "embedded inside larger content."
                            ),
                        )
                    )
                    break

            except (
                ValueError,
                TypeError,
                UnicodeError,
            ):
                continue

        # --------------------------------------------------------------
        # Hex
        # --------------------------------------------------------------

        hex_matches = list(
            cls.HEX_FRAGMENT_RE.finditer(
                text
            )
        )

        for match in hex_matches[
            :cls.MAX_EMBEDDED_PAYLOADS
        ]:
            fragment = match.group(0)

            try:
                decoded = (
                    RecoveryDecoders.hex_decode(
                        fragment
                    )
                )

                (
                    valid,
                    _confidence,
                    _reason,
                ) = RecoveryValidator.validate(
                    "hex",
                    fragment,
                    decoded,
                )

                if valid:
                    candidates.append(
                        DetectionCandidate(
                            transformation="hex",
                            confidence=0.82,
                            reason=(
                                "Detected a valid hexadecimal "
                                "payload embedded inside larger "
                                "content."
                            ),
                        )
                    )
                    break

            except (
                ValueError,
                TypeError,
                UnicodeError,
            ):
                continue

        # --------------------------------------------------------------
        # URL encoding
        # --------------------------------------------------------------

        url_matches = list(
            cls.URL_FRAGMENT_RE.finditer(
                text
            )
        )

        for match in url_matches[
            :cls.MAX_EMBEDDED_PAYLOADS
        ]:
            fragment = match.group(0)

            try:
                decoded = (
                    RecoveryDecoders.url_decode(
                        fragment
                    )
                )

                (
                    valid,
                    _confidence,
                    _reason,
                ) = RecoveryValidator.validate(
                    "url_encoding",
                    fragment,
                    decoded,
                )

                if valid:
                    candidates.append(
                        DetectionCandidate(
                            transformation="url_encoding",
                            confidence=0.80,
                            reason=(
                                "Detected valid percent-encoded "
                                "content embedded inside larger "
                                "text."
                            ),
                        )
                    )
                    break

            except (
                ValueError,
                TypeError,
                UnicodeError,
            ):
                continue

        return candidates

    # ------------------------------------------------------------------
    # Candidate de-duplication
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate_candidates(
        candidates: list[DetectionCandidate],
    ) -> list[DetectionCandidate]:
        """
        Keep the highest-confidence candidate of each type.
        """

        best: dict[
            str,
            DetectionCandidate,
        ] = {}

        for candidate in candidates:

            existing = best.get(
                candidate.transformation
            )

            if (
                existing is None
                or candidate.confidence
                > existing.confidence
            ):
                best[
                    candidate.transformation
                ] = candidate

        return list(
            best.values()
        )

    # ------------------------------------------------------------------
    # Preview helper
    # ------------------------------------------------------------------

    @staticmethod
    def _preview(
        text: Any,
        limit: int = 160,
    ) -> str:
        """
        Create a small preview for recovery metadata.

        The complete artifact is never duplicated into the metadata.
        """

        if isinstance(text, bytes):
            text = text.decode(
                "utf-8",
                errors="replace",
            )

        text = str(text)

        if len(text) <= limit:
            return text

        return (
            text[:limit]
            + "..."
        )