import json
import base64
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.database import get_sync_pool, get_async_pool
from app.vfs import PostgresVFSBackend
from app.agent import create_agent_system, get_opik_tracer
from app.streaming import StreamAccumulator, token_from_stream_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Lazy load agent system
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent_system()
    return _agent


# --- JSON-RPC Model ---

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any]
    id: Optional[int] = None

# --- VFS Requests ---

class VfsWriteRequest(BaseModel):
    path: str
    content: str
    overwrite: bool = True

class VfsEditRequest(BaseModel):
    path: str
    old_string: str
    new_string: str
    replace_all: bool = False

# --- API Routes ---

@router.get("/status")
async def system_status():
    """Runtime status for Milestone 2 verification (DB, Opik, model)."""
    db_ok = False
    vfs_count: int | None = None
    try:
        pool = get_async_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                db_ok = True
                await cur.execute("SELECT COUNT(*) FROM vfs_files")
                row = await cur.fetchone()
                vfs_count = row[0] if row else 0
    except Exception as e:
        logger.warning("Status check: database unavailable: %s", e)

    tracer = get_opik_tracer()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": {"connected": db_ok, "vfs_entries": vfs_count},
        "opik": {
            "configured": bool(settings.OPIK_API_KEY),
            "tracer_ready": tracer is not None,
            "project": settings.OPIK_PROJECT_NAME,
        },
        "model": {
            "provider": settings.DEEPAGENT_MODEL_PROVIDER,
            "name": settings.DEEPAGENT_MODEL_NAME,
        },
        "agent": {
            "subagents": ["researcher", "writer"],
            "loaded": _agent is not None,
        },
    }

@router.post("/rpc")
async def json_rpc_endpoint(req: JsonRpcRequest):
    """Unified JSON-RPC 2.0 endpoint for agent operations.
    Always returns HTTP 200 as per spec; status and error codes are in the response body.
    """
    logger.info("JSON-RPC Request: Method=%s, Id=%s", req.method, req.id)
    
    response_body = {
        "jsonrpc": "2.0",
        "id": req.id
    }
    
    try:
        if req.method == "agent.invoke":
            thread_id = req.params.get("thread_id")
            message = req.params.get("message")
            
            if not thread_id or not message:
                response_body["error"] = {
                    "code": -32602,
                    "message": "Invalid params: thread_id and message are required."
                }
                return response_body
            
            agent = get_agent()
            config = {"configurable": {"thread_id": thread_id}}
            
            # Opik Tracer callback integration
            tracer = get_opik_tracer()
            if tracer:
                config["callbacks"] = [tracer]
            
            # Invoke agent
            # DeepAgents uses LangGraph state schema: {"messages": [...]}
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config=config
            )
            
            # Format output messages
            messages_out = []
            for msg in result.get("messages", []):
                # LangChain Message conversions
                role = "assistant"
                if hasattr(msg, "type"):
                    role = "user" if msg.type == "human" else "assistant"
                elif isinstance(msg, dict):
                    role = msg.get("role", "assistant")
                
                content = ""
                if hasattr(msg, "content"):
                    content = msg.content
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                
                # Filter out system or empty messages from chat response
                if content and role != "system":
                    messages_out.append({
                        "role": role,
                        "content": content
                    })
            
            response_body["result"] = {
                "status": "success",
                "messages": messages_out
            }
            
        else:
            response_body["error"] = {
                "code": -32601,
                "message": f"Method not found: '{req.method}'"
            }
            
    except Exception as e:
        logger.error("JSON-RPC execution error", exc_info=True)
        response_body["error"] = {
            "code": -32603,
            "message": f"Internal error: {str(e)}"
        }
        
    return response_body


@router.get("/agent/stream")
async def stream_agent(
    thread_id: str = Query(..., description="Unique conversation thread ID"),
    message: str = Query(..., description="User message to send to the agent")
):
    """Server-Sent Events (SSE) streaming endpoint for live agent output and logs."""
    
    async def sse_generator():
        try:
            agent = get_agent()
            config = {"configurable": {"thread_id": thread_id}}
            tracer = get_opik_tracer()
            if tracer:
                config["callbacks"] = [tracer]
            
            logger.info("Streaming agent for thread: %s", thread_id)
            stream_acc = StreamAccumulator()

            async for event in agent.astream_events(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                version="v2",
            ):
                event_type = event.get("event")

                parsed = token_from_stream_event(event)
                if parsed:
                    run_id, piece = parsed
                    token = stream_acc.ingest(run_id, piece)
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

                elif event_type == "on_chain_start":
                    name = event.get("name", "chain")
                    yield f"data: {json.dumps({'type': 'log', 'content': f'Starting: {name}'})}\n\n"

                elif event_type == "on_tool_start":
                    name = event.get("name", "tool")
                    inputs = event.get("data", {}).get("input", "")
                    yield f"data: {json.dumps({'type': 'log', 'content': f'Running tool: {name} (args: {inputs})'})}\n\n"

                elif event_type == "on_tool_end":
                    name = event.get("name", "tool")
                    yield f"data: {json.dumps({'type': 'log', 'content': f'Tool {name} completed.'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error("SSE stream error", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            
    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream; charset=utf-8",
    )

# --- VFS API Endpoints ---

@router.get("/vfs/list")
async def vfs_list(path: str = Query("/", description="VFS Directory Path")):
    backend = PostgresVFSBackend()
    res = await backend.als(path)
    if res.error:
        raise HTTPException(status_code=400, detail=res.error)
    return {"entries": res.entries}

@router.get("/vfs/read")
async def vfs_read(path: str = Query(..., description="VFS File Path")):
    backend = PostgresVFSBackend()
    res = await backend.aread(path)
    if res.error:
        raise HTTPException(status_code=400, detail=res.error)
    
    # Return file data structure
    return {
        "path": path,
        "content": res.file_data.get("content"),
        "encoding": res.file_data.get("encoding"),
        "created_at": res.file_data.get("created_at"),
        "modified_at": res.file_data.get("modified_at")
    }

@router.post("/vfs/write")
async def vfs_write(req: VfsWriteRequest):
    backend = PostgresVFSBackend()
    res = await backend.awrite(req.path, req.content, overwrite=req.overwrite)
    if res.error:
        raise HTTPException(status_code=400, detail=res.error)
    return {"status": "success", "path": res.path}

@router.post("/vfs/edit")
async def vfs_edit(req: VfsEditRequest):
    backend = PostgresVFSBackend()
    res = await backend.aedit(
        file_path=req.path,
        old_string=req.old_string,
        new_string=req.new_string,
        replace_all=req.replace_all
    )
    if res.error:
        raise HTTPException(status_code=400, detail=res.error)
    return {"status": "success", "path": res.path, "occurrences": res.occurrences}

@router.delete("/vfs/delete")
async def vfs_delete(path: str = Query(..., description="VFS File Path")):
    try:
        pool = get_async_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Delete target path and recursively delete any descendant paths if it represents a directory
                normalized_path = path if path.endswith('/') else path + '/'
                await cur.execute(
                    "DELETE FROM vfs_files WHERE path = %s OR path LIKE %s;", 
                    (path, f"{normalized_path}%")
                )
        return {"status": "success", "message": f"Successfully deleted '{path}' and all its descendants"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/vfs/upload")
async def vfs_upload(
    path: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        content = await file.read()
        backend = PostgresVFSBackend()
        res = await backend.aupload_files([(path, content)])
        if res[0].error:
            raise HTTPException(status_code=400, detail=res[0].error)
        return {"status": "success", "path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/vfs/download")
async def vfs_download(path: str = Query(..., description="VFS File Path")):
    backend = PostgresVFSBackend()
    res = await backend.adownload_files([path])
    file_res = res[0]
    if file_res.error:
        raise HTTPException(status_code=400, detail=file_res.error)
    
    filename = path.split("/")[-1] or "download"
    return Response(
        content=file_res.content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
