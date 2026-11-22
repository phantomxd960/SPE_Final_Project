import jwt
import pytest

from regdiff_api.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_round_trip():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_garbage_hash_is_rejected_not_raised():
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_token_round_trip():
    token, expires_in = create_token(7, "admin")
    claims = decode_token(token)
    assert claims["sub"] == "7" and claims["role"] == "admin" and expires_in > 0


def test_tampered_token_is_rejected():
    token, _ = create_token(7, "admin")
    with pytest.raises(jwt.PyJWTError):
        decode_token(token[:-2] + "xx")
