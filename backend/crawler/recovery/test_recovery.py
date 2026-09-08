from crawler.recovery.engine import RecoveryEngine


def test_plain_text_is_unchanged():
    text = "This is completely normal text."

    result = RecoveryEngine.process(text)

    assert result.recovered is False
    assert result.recovered_content == text


def test_base64_recovery():
    text = "SGVsbG8gV29ybGQ="

    result = RecoveryEngine.process(text)

    assert result.recovered is True
    assert result.recovered_content == "Hello World"
    assert result.transformations[0]["transformation"] == "base64"


def test_embedded_base64_recovery():
    text = (
        "Seller contact: "
        "aHR0cHM6Ly9leGFtcGxlLmNvbQ=="
    )

    result = RecoveryEngine.process(text)

    assert result.recovered is True
    assert "https://example.com" in result.recovered_content


def test_hex_recovery():
    text = "48656c6c6f20576f726c64"

    result = RecoveryEngine.process(text)

    assert result.recovered is True
    assert result.recovered_content == "Hello World"


def test_url_encoding_recovery():
    text = "hello%20world"

    result = RecoveryEngine.process(text)

    assert result.recovered is True
    assert result.recovered_content == "hello world"


def test_rot13_recovery():
    text = "uryyb jbeyq"

    result = RecoveryEngine.process(text)

    assert result.recovered is True
    assert result.recovered_content == "hello world"


def test_pgp_detection():
    text = """-----BEGIN PGP MESSAGE-----
abcdef
-----END PGP MESSAGE-----"""

    result = RecoveryEngine.process(text)

    assert result.recovered is False
    assert result.status == "encrypted_key_required"
    assert any(
        candidate["transformation"] == "pgp"
        for candidate in result.candidates_considered
    )


def test_original_content_is_preserved():
    text = "SGVsbG8gV29ybGQ="

    result = RecoveryEngine.process(text)

    assert result.original_content == text
    assert result.recovered_content == "Hello World"


def test_empty_content():
    result = RecoveryEngine.process("")

    assert result.recovered is False
    assert result.status == "no_content"