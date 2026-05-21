# server/DESIGN.md (Backend Architecture & Execution)

## Directory Structure

```txt
server/
├── app/
│   ├── __init__.py
│   ├── config.py         # Config loader (pydantic-settings)
│   ├── database.py       # DB pool and tables migration helper
│   ├── vfs.py            # PostgresVFSBackend (inherits deepagents BackendProtocol)
│   ├── agent.py          # Orchestrator & subagents setup with OpikTracer
│   ├── routes.py         # FastAPI Endpoints (Agent chat / VFS admin)
│   └── main.py           # Application Entry Point
├── pyproject.toml        # Poetry/uv python dependencies
├── DESIGN.md             # This file
└── .env                  # Environment Variables
```

---

## Component Internal Design

### 1. `vfs.py` (PostgresVFSBackend)
Implements all sync and async methods of `BackendProtocol`. It uses an `asyncpg` or `psycopg` connection pool to execute queries.
- **Write**: Inserts a new row with `/` relative path. Throws if path already exists.
- **Read**: Selects `content` and `encoding` for the path.
- **Edit**: Performs string replacements on `content` and updates the database row.
- **Ls**: Lists files/directories directly in the directory. If a child has `is_dir=True`, it returns with a trailing `/`.
- **Grep**: Iterates over all files containing the path prefix and searches contents for literal string match.
- **Glob**: Searches paths using fnmatch matching.

### 2. `agent.py` (Multi-Agent system)
- Registers an orchestrator agent using `create_deep_agent`.
- Configures subagents list (`researcher`, `writer`).
- Uses `OpikTracer` callback passed to the agent run configuration for monitoring trace information.

---

## Commands

### Dependencies Sync
```bash
uv sync
```

### Run Server (Development)
```bash
uv run python main.py
```

### Run Tests
```bash
uv run pytest
```
