"""Chiffrement local des données personnelles (Fernet / AES-128-CBC + HMAC).

La clé est stockée dans data/secret.key (droits restreints quand l'OS le permet).
Perdre cette clé rend le profil illisible : elle est incluse dans la procédure de sauvegarde documentée.
"""
from __future__ import annotations

import json
import os
import secrets
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


def _restrict(path) -> None:  # noqa: ANN001
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


@lru_cache
def _fernet() -> Fernet:
    p = get_settings().data_dir / "secret.key"
    if not p.exists():
        p.write_bytes(Fernet.generate_key())
        _restrict(p)
    return Fernet(p.read_bytes().strip())


def reset_crypto_cache() -> None:
    _fernet.cache_clear()


def encrypt_json(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()


def decrypt_json(token: str) -> dict:
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken as e:
        raise ValueError("Impossible de déchiffrer le profil (clé data/secret.key différente ?)") from e


def get_api_token() -> str:
    p = get_settings().data_dir / "token.txt"
    if not p.exists():
        p.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        _restrict(p)
    return p.read_text(encoding="utf-8").strip()
