"""Shared test fixtures for all tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.models.base import Base
from app.models.department import Department
from app.models.user import User


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Make the engine available for other fixtures via the module
    _test_engine = engine
    _test_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Store on the module so db_session can pick it up
    _shared_state = {"engine": _test_engine, "session_factory": _test_session_factory}

    yield _shared_state

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(setup_db):
    """Yield an async database session for testing."""
    session_factory = setup_db["session_factory"]
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    """Yield an httpx AsyncClient with ASGI transport and get_db override."""

    from app.core.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    """Create a Department + User in the DB and return the user."""
    dept = Department(name="Engineering")
    db_session.add(dept)
    await db_session.flush()

    user = User(
        username="testuser",
        password_hash=hash_password("password123"),
        display_name="Test User",
        department_id=dept.id,
        position="Engineer",
        is_dept_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_header(test_user):
    """Return an Authorization header dict with a valid JWT for test_user."""
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}
