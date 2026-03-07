import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.services.database import init_engine

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_engine()
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
