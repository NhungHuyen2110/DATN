
from pwdlib import PasswordHash


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hasher.verify(password, hashed)


COOKIE_NAME = "lumiere_session"
SESSION_DAYS = 7
SESSION_SECONDS = SESSION_DAYS * 24 * 60 * 60
