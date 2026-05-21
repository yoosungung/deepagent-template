# ROADMAP.md (Project Milestones & Implementation Sequence)

This document maps out the milestones, implementation sequence, and open decisions for the SI Agent Scaffolding project.

---

## Execution Sequence

```mermaid
gantt
    title SI Agent Scaffolding Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1
    Scaffolding Setup & Docs     :active, p1, 2026-05-21, 1d
    Backend VFS & Checkpointer   :active, p2, after p1, 2d
    section Phase 2
    Frontend UI Chat & Admin     :after p2, p3, 2d
    Observability (Opik) Setup   :after p3, p4, 1d
    section Phase 3
    K8s Deployment & MCPs        :after p4, p5, 2d
```

---

## Milestones

### Milestone 1: Core Scaffolding (Phase 1) — **Complete**
- [x] Initial design files (AGENTS.md, ARCHITECTURE.md, ROADMAP.md, README.md).
- [x] Backend FastAPI codebase initialization (`server/app/main.py`, `routes.py`, `config.py`).
- [x] Implementation of `PostgresVFSBackend` (VFS table, sync/async file operations, REST `/api/vfs/*`).
- [x] Integration of LangGraph Postgres thread checkpointer (`PostgresSaver` + `checkpointer.setup()` on agent init).
- [x] M1 verification: server boot + VFS list/read against live Postgres; checkpoint tables created on startup via `init_db()`.

### Milestone 2: Agent Interaction & VFS UI (Phase 2) — **Complete**
- [x] Orchestrator Agent configuration with specialized Subagents (`researcher`, `writer` in `server/app/agent.py`).
- [x] Admin UI folder tree view and online file editor (`client/src/components/AdminView.tsx`, collapsible tree).
- [x] Real-time Chat Panel with LLM output streaming (SSE + `StreamAccumulator` dedup, 22 unit tests in `server/tests/test_streaming.py`).
- [x] Opik tracing integration (`get_opik_tracer()` when `OPIK_API_KEY` set); verify via `GET /api/status`.
- [ ] M2 optional: live Opik dashboard walkthrough with cloud/self-hosted instance.

### Milestone 3: Production Delivery & MCPs (Phase 3)
- [ ] Kubernetes base deployment manifest files setup.
- [ ] CI/CD configuration via GitHub workflows.
- [ ] MCP (Model Context Protocol) component design and guidelines.

---

## Open Decisions (Unresolved Items)

1. **Authentication Mode**:
   - Currently, the template rules suggest basic JWT verification. Should we implement OAuth2 or keep it simple with JWT and an API key header?
   - *Decision*: Simple Bearer Token JWT scheme initially, pluggable for corporate SSO.
2. **VFS File Syncing/Caching**:
   - Should subagents read files directly from the DB on every operation, or cache them in-memory?
   - *Decision*: Read directly from database to avoid caching bugs, as database accesses are fast.
