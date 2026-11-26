from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as app_db
from app.db import Base, get_session, make_engine
from app.main import app
from scripts.seed_dev import load

SAMPLE = Path(__file__).resolve().parents[2] / "sample-data"


@pytest.fixture(scope="session")
def engine():
    eng = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        load(s, SAMPLE)
    return eng


@pytest.fixture(scope="session")
def client(engine):
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = override
    app_db.SessionLocal = TestSession  # health check
    import app.main as main_mod

    main_mod.SessionLocal = TestSession
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
