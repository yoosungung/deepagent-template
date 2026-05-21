import logging
from pathlib import Path

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from app.config import settings

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
                agents_md_path = Path(__file__).resolve().parent.parent.parent / "AGENTS.md"
                if agents_md_path.is_file():
                    agents_md_content = agents_md_path.read_text(encoding="utf-8")
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
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    ("/memory/reports/", "", True, 0)
                )

                skill_dir = "/skills/research_assistant/"
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    (skill_dir, "", True, 0)
                )

                skill_md = """---
name: Research Assistant
description: Naver 웹 검색으로 자료를 수집하고 `/memory/`에 원자료를 저장하는 스킬.
allowed_tools: [web_search, ls, read_file, write_file, edit_file, glob, grep]
---
# Research Skill

조사 작업을 시작하기 전에 아래 체크리스트를 따른다.

## 시작 전 체크리스트
1. `ls /memory/`로 기존 조사 파일을 확인한다.
2. 동일 주제의 `research_*.md`가 있으면 `read_file` 후 `edit_file`로 보강한다.
3. 검색어는 한국어로 작성한다.

## 검색 절차
1. `web_search(query)`를 1~3회 호출한다. 시도마다 키워드를 바꿔 교차 확인한다.
2. 결과 항목의 URL, 제목, 요약을 그대로 보존한다 (재해석 금지).

## 저장 규칙
- 경로: `/memory/research_<영문_slug>.md`
- 포맷:

```markdown
---
topic: <주제>
queries: [<쿼리1>, <쿼리2>]
collected_at: <ISO datetime>
---
# <주제>

## 핵심 발견
- 불릿 3~7개 (사실 위주)

## 원자료
1. <기사 제목>
   - URL: <링크>
   - 요약: <2~3문장>
```

## 금지 사항
- 의견·해석·결론 작성 (writer가 담당)
- 출처(URL) 누락
- 검색 없이 추측으로 답변
"""
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    (f"{skill_dir}SKILL.md", skill_md, False, len(skill_md))
                )

                writer_skill_dir = "/skills/report_writer/"
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    (writer_skill_dir, "", True, 0)
                )

                writer_skill_md = """---
name: Report Writer
description: `/memory/`의 조사 자료를 바탕으로 한국어 markdown 보고서를 작성하는 스킬.
allowed_tools: [ls, read_file, write_file, edit_file, glob, grep]
---
# Report Writer Skill

## 시작 전 체크리스트
1. `ls /memory/`로 자료 목록을 확인한다.
2. 주제와 관련된 `research_*.md`를 `read_file`로 모두 읽는다.
3. 자료가 부족하면 작성을 중단하고 Orchestrator에게 researcher 호출이 필요함을 보고한다.

## 작성 규칙
- 한국어 markdown으로 작성한다.
- 사실 문장은 가능한 한 인용을 붙인다 (`/memory/...` 파일명 또는 URL).
- `/memory/`에 없는 정보를 임의로 만들어내지 않는다.
- 자체 web 검색을 하지 않는다.

## 저장 규칙
- 경로: `/memory/reports/<영문_slug>.md`
- 사용자가 다른 경로를 지정하면 그에 따른다.

## 문서 구조

```markdown
# <제목>

> 요약: <3~5문장>

## 배경
## 주요 내용
## 시사점 / 권고
## 참고 자료
- [<제목>](<URL>) — `/memory/research_xxx.md`
```
"""
                cur.execute(
                    "INSERT INTO vfs_files (path, content, is_dir, size) VALUES (%s, %s, %s, %s);",
                    (f"{writer_skill_dir}SKILL.md", writer_skill_md, False, len(writer_skill_md))
                )
                
                logger.info("Initial seed completed.")

    # LangGraph checkpointer tables (requires autocommit for migrations)
    with PostgresSaver.from_conn_string(CONN_INFO) as checkpointer:
        checkpointer.setup()

    logger.info("Database initialization completed successfully.")
