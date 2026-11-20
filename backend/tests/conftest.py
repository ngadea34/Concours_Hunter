import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CH_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CH_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("CH_MIN_DELAY_PER_DOMAIN_S", "0")
    from app.config import reset_settings_cache
    from app.db.session import dispose_engine
    from app.security.crypto import reset_crypto_cache

    reset_settings_cache()
    dispose_engine()
    reset_crypto_cache()
    from app.db.migrations import migrate

    migrate()
    yield tmp_path
    dispose_engine()
    reset_settings_cache()
    reset_crypto_cache()


@pytest.fixture()
def db(env):
    from app.db.session import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client(env):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def rules(name: str) -> str:
    return (FIX / "rules" / name).read_text(encoding="utf-8")


def make_contest(db, title="Gagnez une PS5", url="https://jouets-exemple.test/jeu", rules_text=None, **kw):
    from app.db.models import Contest
    from app.discovery.pipeline import fingerprint
    from app.intelligence.qualify import add_rules, qualify
    from app.security.sanitize import canonical_url

    c = Contest(title=title, url=url, canonical_url=canonical_url(url), fingerprint=fingerprint(title, None), **kw)
    db.add(c)
    db.flush()
    if rules_text:
        add_rules(db, c, rules_text, url + "/reglement", "fetched")
    qualify(db, c)
    db.commit()
    return c
