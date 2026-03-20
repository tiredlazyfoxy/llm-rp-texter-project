import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.admin.db_management import router as db_management_router
from app.routes.admin.users import router as admin_users_router
from app.routes.admin.worlds import router as worlds_router
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.llm_chat import router as llm_chat_router
from app.routes.llm_models import router as llm_models_router
from app.routes.llm_servers import router as llm_servers_router
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
app.include_router(chat_router)
app.include_router(admin_users_router)
app.include_router(db_management_router)
app.include_router(llm_servers_router)
app.include_router(llm_models_router)
app.include_router(llm_chat_router)
app.include_router(worlds_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
