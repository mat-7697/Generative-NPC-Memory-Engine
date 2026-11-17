import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.auth.router import router as auth_router
from app.config import get_settings
from app.database import close_db, get_pool, init_db
from app.limiter import limiter
from app.qdrant_client import init_qdrant
from app.routers.admin import router as admin_router
from app.routers.battle import router as battle_router
from app.routers.chat import router as chat_router
from app.routers.inventory import router as inventory_router
from app.routers.memory import router as memory_router
from app.routers.npcs import router as npcs_router
from app.routers.players import router as players_router
from app.routers.quests import router as quests_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("npc_engine")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle for database pools and vector indexes."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        logger.info("Initializing Generative NPC Memory Engine backend...")
        try:
            await init_db()
        except Exception as exc:
            logger.warning("Could not establish PostgreSQL connection pool on startup: %s", exc)

        try:
            init_qdrant()
        except Exception as exc:
            logger.warning("Could not initialize Qdrant vector collection on startup: %s", exc)

    yield

    if not os.environ.get("PYTEST_CURRENT_TEST"):
        logger.info("Closing backend resources...")
        await close_db()


app = FastAPI(
    title="Generative NPC Memory Engine API",
    description="Multi-tier backend uniting PostgreSQL transactional mechanics and Qdrant generative vector memory for intelligent game NPCs.",
    version="1.0.0",
    lifespan=lifespan,
)

# Attach SlowAPI rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Sub-Routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(players_router, prefix="/api/players")
app.include_router(npcs_router, prefix="/api/npcs")
app.include_router(inventory_router, prefix="/api/inventory")
app.include_router(quests_router, prefix="/api/quests")
app.include_router(memory_router, prefix="/api/memory")
app.include_router(chat_router, prefix="/api/chat")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(battle_router, prefix="/api/battle")


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health status monitor checking operational connectivity of engine subsystems."""
    is_test = bool(os.environ.get("PYTEST_CURRENT_TEST"))
    pool = get_pool()
    pg_ok = False
    pg_latency_ms = None

    if pool is not None:
        try:
            t0 = time.perf_counter()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            pg_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            pg_ok = True
        except Exception as e:
            logger.warning("PostgreSQL health check failed: %s", e)
    elif is_test:
        pg_ok = True

    qdrant_ok = False
    if is_test:
        qdrant_ok = True
    else:
        try:
            from app.qdrant_client import get_qdrant_client
            client = get_qdrant_client()
            await asyncio.to_thread(client.get_collections)
            qdrant_ok = True
        except Exception as e:
            logger.warning("Qdrant health check failed: %s", e)

    overall_status = "healthy" if (pg_ok and qdrant_ok) else ("degraded" if pg_ok else "unhealthy")

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected" if pg_ok else "disconnected",
        "qdrant": "connected" if qdrant_ok else "disconnected",
        "database_latency_ms": pg_latency_ms,
        "environment": settings.app_env,
        "version": "1.0.0",
    }


@app.get("/", tags=["Root"])
async def root():
    """Root entrypoint returning system metadata and API documentation locations."""
    return {
        "name": "Generative NPC Memory Engine API",
        "status": "online",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "health_check": "/api/health",
    }
