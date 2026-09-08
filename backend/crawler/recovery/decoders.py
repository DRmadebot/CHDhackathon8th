from __future__ import annotations

import base64
import binascii
from urllib.parse import unquote


class RecoveryDecoders:
    """
    Deterministic decoders/de-obfuscators used by RecoveryEngine.

    These functions do not decide whether a transformation is appropriate.
    That decision belongs to RecoveryDetector + RecoveryValidator.
    """

    @staticmethod
    def base64_decode(text: str) -> str | bytes:
        """
        Decode a Base64 payload.

        Returns:
            UTF-8 text when possible, otherwise raw bytes.
        """
        try:
            decoded = base64.b64decode(
                text,
                validate=True,
            )
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid Base64 input.") from exc

        return RecoveryDecoders._bytes_to_text_or_bytes(decoded)

    @staticmethod
    def base32_decode(text: str) -> str | bytes:
        """
        Decode a Base32 payload.
        """
        try:
            decoded = base64.b32decode(
                text,
                casefold=True,
            )
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid Base32 input.") from exc

        return RecoveryDecoders._bytes_to_text_or_bytes(decoded)

    @staticmethod
    def hex_decode(text: str) -> str | bytes:
        """
        Decode hexadecimal bytes.
        """
        try:
            decoded = bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("Invalid hexadecimal input.") from exc

        return RecoveryDecoders._bytes_to_text_or_bytes(decoded)

    @staticmethod
    def url_decode(text: str) -> str:
        """
        Decode percent-encoded URL/text content.

        Example:
            hello%20world -> hello world
        """
        return unquote(text)

    @staticmethod
    def rot13_decode(text: str) -> str:
        """
        ROT13 is its own inverse, so decoding is equivalent to
        applying ROT13 once.
        """
        result = []

        for char in text:
            if "a" <= char <= "z":
                result.append(
                    chr(
                        (ord(char) - ord("a") + 13) % 26
                        + ord("a")
                    )
                )
            elif "A" <= char <= "Z":
                result.append(
                    chr(
                        (ord(char) - ord("A") + 13) % 26
                        + ord("A")
                    )
                )
            else:
                result.append(char)

        return "".join(result)

    @staticmethod
    def caesar_decode(text: str, shift: int) -> str:
        """
        Reverse a Caesar shift.

        Example:
            ciphertext = khoor
            shift = 3
            result = hello
        """
        if not 0 <= shift <= 25:
            raise ValueError("Caesar shift must be between 0 and 25.")

        result = []

        for char in text:
            if "a" <= char <= "z":
                result.append(
                    chr(
                        (ord(char) - ord("a") - shift) % 26
                        + ord("a")
                    )
                )
            elif "A" <= char <= "Z":
                result.append(
                    chr(
                        (ord(char) - ord("A") - shift) % 26
                        + ord("A")
                    )
                )
            else:
                result.append(char)

        return "".join(result)

    @staticmethod
    def _bytes_to_text_or_bytes(data: bytes) -> str | bytes:
        """
        Prefer UTF-8 when the decoded bytes represent text.
        Otherwise preserve the binary result.
        """
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data