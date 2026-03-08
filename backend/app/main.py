import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.db import engine as db_engine
from app.db.engine import DbConfig
from app.services import vector_storage

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def _build_config() -> DbConfig | None:
    """Build DB config from environment variables, or None for defaults."""
    db_path_env = os.environ.get("LLMRP_DB_PATH")
    if db_path_env:
        return DbConfig(db_path=Path(db_path_env))
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = _build_config()
    await db_engine.init_engine(config)

    # Vector store — co-locate with DB if custom path
    vector_dir = None
    if config is not None:
        vector_dir = config.db_path.parent / "vector"
    await vector_storage.init_vector_store(vector_dir)
    yield


app = FastAPI(title="LLMRP Backend", version="0.1.0", lifespan=lifespan)

# CORS — dev only (prod uses nginx same-origin proxy)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8094"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
