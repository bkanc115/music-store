from app.security import hash_password, verify_password


def test_password_hash_roundtrip():
    stored = hash_password("s3cret-pass")
    assert stored != "s3cret-pass"
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("other", stored)


def test_same_password_different_salt():
    assert hash_password("abc12345") != hash_password("abc12345")


def test_malformed_hash_is_rejected():
    assert not verify_password("x", "garbage")
