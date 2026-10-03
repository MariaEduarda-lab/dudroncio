from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type


_PASSWORD_HASHER = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """Deriva a senha com Argon2id e salt aleatorio."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded_password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(encoded_password, password)
    except (InvalidHashError, VerificationError):
        return False
