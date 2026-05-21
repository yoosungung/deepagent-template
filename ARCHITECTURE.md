# ARCHITECTURE.md (Immutable Contracts & Interfaces)

## Immutable Rules

1. **JSON-RPC Over HTTP**: All client-backend API interactions for conversation/agent tasks follow JSON-RPC 2.0. HTTP response status is ALWAYS `200 OK` (errors are returned in the JSON payload body).
2. **Postgres-Centric State**: The system must NOT maintain persistent local state on the server's disk.
   - All conversation threads and checkpoint history are stored in Postgres (`langgraph-checkpoint-postgres`).
   - All workspace folders, files, and skills are stored in Postgres via the `PostgresVFSBackend` custom virtual file system implementation.
3. **Opik Observability**: Every agent invocation must pass the `OpikTracer` callback when configured.
4. **VFS File Ownership**: Directory paths in the VFS must strictly start with `/`. The workspace root corresponds to `/`.

---

## DB Schema Design

### 1. `vfs_files` Table
Stores all agent documents, skills, and memory.
```sql
CREATE TABLE IF NOT EXISTS vfs_files (
    path VARCHAR(1024) PRIMARY KEY,
    content TEXT NOT NULL,
    encoding VARCHAR(50) DEFAULT 'utf-8',
    is_dir BOOLEAN DEFAULT FALSE,
    size INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## API & Interface Schemas

All api endpoints are exposed under `/api`.

### 1. Agent Interaction API
**Endpoint**: `POST /api/rpc`
**Format**: JSON-RPC 2.0

#### Request: Initiate/Resume Agent Run
```json
{
  "jsonrpc": "2.0",
  "method": "agent.invoke",
  "params": {
    "thread_id": "thread_abc123",
    "message": "Research SI agent scaffolding projects and compile a report."
  },
  "id": 1
}
```

#### Response: Success
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "messages": [
      {
        "role": "assistant",
        "content": "Report successfully created in VFS at `/memory/scaffolding_report.md`."
      }
    ]
  },
  "id": 1
}
```

### 2. VFS Filesystem Admin API
**Endpoints**:
- `GET /api/vfs/list?path={path}`: Lists directory contents.
- `GET /api/vfs/read?path={path}`: Reads a file.
- `POST /api/vfs/write`: Writes/Creates a file.
- `POST /api/vfs/edit`: Performs string replacement in a file.
- `DELETE /api/vfs/delete?path={path}`: Deletes a file.
- `POST /api/vfs/upload`: Uploads binary/text files.
- `GET /api/vfs/download?path={path}`: Downloads binary/text files.

#### VFS Item Schema:
```json
{
  "path": "/skills/calculator/SKILL.md",
  "is_dir": false,
  "size": 204,
  "modified_at": "2026-05-21T10:45:00Z"
}
```
