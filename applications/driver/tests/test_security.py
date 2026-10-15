from app.auth.security import hash_password, verify_password
from app.email.gmail import safe_filename, sha256_bytes


def test_password_hash_roundtrip():
    encoded = hash_password("senha-segura-123")
    assert verify_password("senha-segura-123", encoded)
    assert not verify_password("errada", encoded)
    assert "senha-segura-123" not in encoded


def test_email_helpers():
    assert safe_filename("../../x?.pdf") == "x_.pdf"
    assert sha256_bytes(b"hello").startswith("2cf24dba")


def test_tailscale_source_filter_ranges():
    from app.main import source_is_allowed

    assert source_is_allowed("127.0.0.1")
    assert source_is_allowed("100.64.0.1")
    assert source_is_allowed("100.127.255.254")
    assert source_is_allowed("fd7a:115c:a1e0::1234")
    assert not source_is_allowed("192.168.1.25")
    assert not source_is_allowed("8.8.8.8")
