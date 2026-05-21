import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

from app.database import init_db, get_sync_pool, get_async_pool, open_async_pool
from app.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    logger.info("Starting up server...")
    try:
        init_db()
        await open_async_pool()
    except Exception as e:
        logger.error("Failed to initialize database during startup", exc_info=True)
    
    yield
    
    # Shutdown: close database pools
    logger.info("Shutting down server...")
    try:
        sync_pool = get_sync_pool()
        sync_pool.close()
    except Exception:
        pass
    try:
        async_pool = get_async_pool()
        await async_pool.close()
    except Exception:
        pass

app = FastAPI(
    title="SI Agent Scaffolding API",
    description="FastAPI + DeepAgents backend scaffolding with Postgres VFS & Thread Persistence",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configurations
# Allowing React dev server (5173) and any other origins in dev mode
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "SI Agent Scaffolding API is running."}
