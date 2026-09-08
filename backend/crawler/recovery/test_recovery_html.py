from crawler.recovery.engine import RecoveryEngine


def test_base64_inside_html():
    html = """
    <html>
        <body>
            <h1>Marketplace Listing</h1>
            <p>Seller contact:</p>
            <p>SGVsbG8gV29ybGQ=</p>
        </body>
    </html>
    """

    result = RecoveryEngine.process(html)

    assert result.recovered is True
    assert "Hello World" in result.recovered_content


def test_multiple_encoded_values_inside_html():
    html = """
    <html>
        <body>
            <p>Seller: John</p>
            <p>Contact: SGVsbG8gV29ybGQ=</p>
            <p>Other: 48656c6c6f</p>
        </body>
    </html>
    """

    result = RecoveryEngine.process(html)

    assert result.recovered is True


def test_normal_html_is_not_modified():
    html = """
    <html>
        <body>
            <h1>Normal marketplace</h1>
            <p>Seller sells shoes.</p>
        </body>
    </html>
    """

    result = RecoveryEngine.process(html)

    assert result.recovered is False


def test_original_html_is_preserved():
    html = """
    <html>
        <body>
            <p>SGVsbG8gV29ybGQ=</p>
        </body>
    </html>
    """

    result = RecoveryEngine.process(html)

    assert result.original_content == html


def test_pgp_html_detection():
    html = """
    <html>
        <body>
            <p>Encrypted message:</p>
            <pre>
-----BEGIN PGP MESSAGE-----
abcdef
-----END PGP MESSAGE-----
            </pre>
        </body>
    </html>
    """

    result = RecoveryEngine.process(html)

    assert result.status == "encrypted_key_required"