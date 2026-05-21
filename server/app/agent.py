import logging
from typing import Optional

from opik.integrations.langchain import OpikTracer
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent
from deepagents.middleware.filesystem import FilesystemPermission

from app.config import settings
from app.database import get_async_pool
from app.tools import web_search
from app.vfs import PostgresVFSBackend

logger = logging.getLogger(__name__)

def get_model_spec() -> str:
    """Return a `provider:model` spec for deepagents / init_chat_model."""
    provider = settings.DEEPAGENT_MODEL_PROVIDER.lower()
    model_name = settings.DEEPAGENT_MODEL_NAME

    known_providers = {
        "openai": "openai",
        "anthropic": "anthropic",
        "gemini": "google_genai",
    }
    if provider not in known_providers:
        logger.warning(
            "Unknown provider '%s', falling back to openai:%s",
            provider,
            model_name,
        )
    provider_prefix = known_providers.get(provider, "openai")

    spec = f"{provider_prefix}:{model_name}"
    logger.info("Using model spec: %s", spec)
    return spec

def get_opik_tracer() -> Optional[OpikTracer]:
    """Return OpikTracer only when a real API key is configured."""
    if not settings.OPIK_API_KEY:
        return None
    try:
        logger.info("Initializing OpikTracer for project: %s", settings.OPIK_PROJECT_NAME)
        return OpikTracer(project_name=settings.OPIK_PROJECT_NAME)
    except Exception as e:
        logger.warning("Failed to initialize OpikTracer: %s", e)
    return None

def create_agent_system():
    """Build and compile the main Orchestrator agent and its specialized subagents."""
    model = get_model_spec()
    
    # Async checkpointer for astream_events / ainvoke (SSE streaming)
    logger.info("Initializing AsyncPostgresSaver checkpointer...")
    checkpointer = AsyncPostgresSaver(get_async_pool())
    
    # Initialize VFS Backend
    vfs_backend = PostgresVFSBackend()
    
    # Configure permissions
    # Let agents read/write anywhere in our virtual space
    permissions = [
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/**"],
            mode="allow",
        )
    ]
    
    # Define Specialized Subagents
    researcher_subagent: SubAgent = {
        "name": "researcher",
        "description": "Used for retrieving information, searching the web, and compiling factual summaries. Saves raw facts in VFS under `/memory/`.",
        "system_prompt": (
            "You are a specialized Research Agent.\n"
            "Your task is to conduct deep research using the web search tool.\n"
            "Save raw research findings to the Virtual File System under the `/memory/` folder (e.g. `/memory/research_results.md`).\n"
            "Do not write final deliverables or polished articles. Just gather and record facts."
        ),
        "tools": [web_search],
        "model": model,
        "permissions": permissions
    }
    
    writer_subagent: SubAgent = {
        "name": "writer",
        "description": "Used for writing documentation, final summaries, articles, or editing VFS files like AGENTS.md based on research inputs.",
        "system_prompt": (
            "You are a specialized Writing Agent.\n"
            "Your task is to read raw research findings from `/memory/` and produce polished, beautiful markdown documents.\n"
            "Save your final documents back to the VFS (e.g. update `/AGENTS.md` or write `/memory/final_report.md`).\n"
            "Format your outputs beautifully using markdown. Do not do web searches yourself; rely on the research outputs."
        ),
        "tools": [],
        "model": model,
        "permissions": permissions
    }
    
    # Build Orchestrator Agent
    logger.info("Creating Orchestrator Agent...")
    orchestrator = create_deep_agent(
        model=model,
        system_prompt=(
            "You are the Orchestrator Agent, the main entry point for the agentic system.\n"
            "Your goal is to coordinate the execution of complex tasks for the user.\n"
            "You have access to a Virtual File System (VFS) containing `/AGENTS.md`, `/skills/`, and `/memory/`.\n"
            "For information gathering, delegate to the `researcher` subagent.\n"
            "For writing, formatting, or updating files, delegate to the `writer` subagent.\n"
            "Always save intermediate states or findings in the VFS so that you and the subagents share a consistent view of the workspace."
        ),
        tools=[],
        subagents=[researcher_subagent, writer_subagent],
        permissions=permissions,
        backend=vfs_backend,
        checkpointer=checkpointer,
        skills=["/skills/research_assistant/"] # Scan skills folder in VFS
    )
    
    return orchestrator
