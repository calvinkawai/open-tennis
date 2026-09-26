import base64
import binascii
import hashlib
import hmac


def owner_authorized(header: str | None, username: str, password: str) -> bool:
    if not header or len(header) > 4096:
        return False
    scheme, separator, encoded = header.partition(" ")
    if not separator or scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeError, ValueError):
        return False
    supplied_user, separator, supplied_password = decoded.partition(":")
    if not separator:
        return False
    valid_user = hmac.compare_digest(
        hashlib.sha256(supplied_user.encode()).digest(),
        hashlib.sha256(username.encode()).digest(),
    )
    valid_password = hmac.compare_digest(
        hashlib.sha256(supplied_password.encode()).digest(),
        hashlib.sha256(password.encode()).digest(),
    )
    return valid_user and valid_password
