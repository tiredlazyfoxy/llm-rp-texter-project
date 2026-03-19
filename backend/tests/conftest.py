import asyncio
from pathlib import Path

import pytest

from app.db.engine import DbConfig, init_engine
from app.services import vector_storage


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def test_db(tmp_path_factory: pytest.TempPathFactory):
    """Initialize DB engine and vector store with temp paths for the entire test session."""
    tmp_dir: Path = tmp_path_factory.mktemp("test_data")

    # DB — temp SQLite file
    db_path = tmp_dir / "test.db"
    config = DbConfig(db_path=db_path, echo=False)
    await init_engine(config)

    # Vector store — temp directory
    vector_dir = tmp_dir / "vector"
    await vector_storage.init_vector_store(vector_dir)

    yield db_path
