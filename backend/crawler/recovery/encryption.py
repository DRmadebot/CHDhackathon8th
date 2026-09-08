from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class EncryptionDetection:
    """
    Result of deterministic encryption-format detection.
    """

    detected: bool
    encryption_type: Optional[str]
    confidence: float
    status: str
    reason: str


class EncryptionHandler:
    """
    Detects known encrypted artifacts.

    This module does NOT attempt to break encryption.

    It currently recognizes OpenPGP ASCII-armored artifacts and
    determines whether the artifact can potentially proceed to an
    authorized decryption step.
    """

    PGP_MARKERS = {
        "message": (
            "-----BEGIN PGP MESSAGE-----",
            "-----END PGP MESSAGE-----",
        ),
        "signed_message": (
            "-----BEGIN PGP SIGNED MESSAGE-----",
        ),
        "public_key": (
            "-----BEGIN PGP PUBLIC KEY BLOCK-----",
            "-----END PGP PUBLIC KEY BLOCK-----",
        ),
        "private_key": (
            "-----BEGIN PGP PRIVATE KEY BLOCK-----",
            "-----END PGP PRIVATE KEY BLOCK-----",
        ),
    }

    PGP_BEGIN_RE = re.compile(
        r"-----BEGIN PGP ([A-Z0-9 ]+)-----"
    )

    @classmethod
    def detect(cls, text: str | None) -> EncryptionDetection:
        """
        Deterministically detect known encryption-related formats.

        This does not perform decryption.
        """

        if not text:
            return EncryptionDetection(
                detected=False,
                encryption_type=None,
                confidence=0.0,
                status="not_detected",
                reason="No content supplied.",
            )

        # ----------------------------------------------------------
        # OpenPGP ASCII armor
        # ----------------------------------------------------------

        if "-----BEGIN PGP MESSAGE-----" in text:
            return EncryptionDetection(
                detected=True,
                encryption_type="pgp",
                confidence=0.99,
                status="encrypted",
                reason=(
                    "Recognized an ASCII-armored OpenPGP encrypted "
                    "message."
                ),
            )

        if "-----BEGIN PGP SIGNED MESSAGE-----" in text:
            return EncryptionDetection(
                detected=True,
                encryption_type="pgp_signed_message",
                confidence=0.99,
                status="signed",
                reason=(
                    "Recognized an ASCII-armored OpenPGP signed message."
                ),
            )

        if "-----BEGIN PGP PUBLIC KEY BLOCK-----" in text:
            return EncryptionDetection(
                detected=True,
                encryption_type="pgp_public_key",
                confidence=0.99,
                status="key_material",
                reason=(
                    "Recognized an ASCII-armored OpenPGP public key block."
                ),
            )

        if "-----BEGIN PGP PRIVATE KEY BLOCK-----" in text:
            return EncryptionDetection(
                detected=True,
                encryption_type="pgp_private_key",
                confidence=0.99,
                status="key_material",
                reason=(
                    "Recognized an ASCII-armored OpenPGP private key block."
                ),
            )

        # ----------------------------------------------------------
        # Unknown PGP armor
        # ----------------------------------------------------------

        match = cls.PGP_BEGIN_RE.search(text)

        if match:
            block_type = match.group(1).strip()

            return EncryptionDetection(
                detected=True,
                encryption_type=f"pgp_{block_type.lower()}",
                confidence=0.97,
                status="pgp_artifact",
                reason=(
                    f"Recognized an OpenPGP ASCII armor marker: "
                    f"{block_type}."
                ),
            )

        # ----------------------------------------------------------
        # Nothing confidently recognizable
        # ----------------------------------------------------------

        return EncryptionDetection(
            detected=False,
            encryption_type=None,
            confidence=0.0,
            status="not_detected",
            reason=(
                "No known encryption format was confidently identified."
            ),
        )

    @classmethod
    def decryption_status(
        cls,
        detection: EncryptionDetection,
        has_authorized_key: bool,
    ) -> str:
        """
        Determines what the system should do next.

        No cryptographic operation is performed here.
        """

        if not detection.detected:
            return "not_encrypted"

        if detection.encryption_type != "pgp":
            return "no_decryption_handler"

        if has_authorized_key:
            return "ready_for_authorized_decryption"

        return "encrypted_key_unavailable"