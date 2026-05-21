import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Connection string
CONN_INFO = settings.DATABASE_URL

# Pools
_sync_pool = None
_async_pool = None

def get_sync_pool() -> ConnectionPool:
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = ConnectionPool(conninfo=CONN_INFO, open=True)
    return _sync_pool

def get_async_pool() -> AsyncConnectionPool:
    """Return the async pool (opened during FastAPI lifespan)."""
    global _async_pool
    if _async_pool is None:
        _async_pool = AsyncConnectionPool(conninfo=CONN_INFO, open=False)
    return _async_pool


async def open_async_pool() -> AsyncConnectionPool:
    pool = get_async_pool()
    await pool.open()
    return pool

def init_db():
    """Sync database table initialization and checkpointer setup."""
    logger.info("Initializing database schemas...")
    
    # Initialize checkpointer table using standard psycopg
    with psycopg.connect(CONN_INFO, autocommit=True) as conn:
        with conn.cursor() as cur:
            # 1. Create VFS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vfs_files (
                    path VARCHAR(1024) PRIMARY KEY,
                    content TEXT NOT NULL,
                    encoding VARCHAR(50) DEFAULT 'utf-8',
                    is_dir BOOLEAN DEFAULT FALSE,
                    size INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create pattern ops index for fast LIKE prefix searches
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_vfs_files_path_pattern 
                ON vfs_files (path varchar_pattern_ops);
            """)
            
            # Seed initial VFS files if empty
            cur.execute("SELECT COUNT(*) FROM vfs_files;")
            count = cur.fetchone()[0]
            if count == 0:
                logger.info("Seeding initial VFS files...")
                # Seed root AGENTS.md
                import os
                agents_md_path = "../AGENTS.md"
                agents_md_content = ""
                if os.path.exists(agents_md_path):
                    with open(agents_md_path, "r", encoding="utf-8") as f:
                        agents_md_content = f.read()
                else:
                    agents_md_content = "# AGENTS.md\nWorkspace seeded successfully."
                
                # Insert AGENTS.md
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    ("/AGENTS.md", agents_md_content, False, len(agents_md_content))
                )
                
                # Seed directories
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    ("/skills/", "", True, 0)
                )
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    ("/memory/", "", True, 0)
                )
                
                # Seed a default skill
                skill_dir = "/skills/research_assistant/"
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    (skill_dir, "", True, 0)
                )
                
                skill_md = """---
name: Web Search
description: Search the web for information using Google or Naver.
allowed_tools: [web_search]
---
# Research Skill
Use this skill when you need to research a topic.
"""
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    (f"{skill_dir}SKILL.md", skill_md, False, len(skill_md))
                )
                
                logger.info("Initial seed completed.")

    # LangGraph checkpointer tables (requires autocommit for migrations)
    with PostgresSaver.from_conn_string(CONN_INFO) as checkpointer:
        checkpointer.setup()

    logger.info("Database initialization completed successfully.")
