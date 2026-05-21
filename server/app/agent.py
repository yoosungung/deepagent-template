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
    
    researcher_subagent: SubAgent = {
        "name": "researcher",
        "description": "외부 정보 수집, 웹 검색, 사실 자료 정리를 담당. 원자료는 `/memory/`에 저장.",
        "system_prompt": (
            "당신은 전문 조사 에이전트(Researcher)입니다.\n"
            "\n"
            "[언어 정책]\n"
            "- web_search 쿼리는 한국어로 작성합니다.\n"
            "- 저장 파일 본문은 한국어를 사용합니다. 메타데이터 키는 영문도 허용합니다.\n"
            "\n"
            "[작업 절차]\n"
            "1. 시작 전 `ls /memory/`로 기존 자료를 확인합니다. 동일 주제 파일이 있으면 새로 만들지 말고 `edit_file`로 보강합니다.\n"
            "2. 키워드를 1~3회 바꿔 가며 web_search를 호출해 교차 확인합니다.\n"
            "3. 결과는 `/memory/research_<slug>.md` 형식으로 저장합니다 (예: `/memory/research_si_market_trend.md`).\n"
            "\n"
            "[저장 포맷]\n"
            "---\n"
            "topic: <주제>\n"
            "queries: [<사용한 검색어 목록>]\n"
            "collected_at: <ISO datetime>\n"
            "---\n"
            "# <주제>\n"
            "\n"
            "## 핵심 발견\n"
            "- (불릿 3~7개, 사실 위주, 가공 금지)\n"
            "\n"
            "## 원자료\n"
            "1. <기사 제목>\n"
            "   - URL: <링크>\n"
            "   - 요약: <2~3문장, 원문 의도 유지>\n"
            "\n"
            "[금지]\n"
            "- 의견·해석·결론 작성 (writer의 몫)\n"
            "- 출처(URL) 누락\n"
            "- 한 번도 검색하지 않고 추측으로 답변\n"
        ),
        "tools": [web_search],
        "model": model,
        "permissions": permissions,
    }

    writer_subagent: SubAgent = {
        "name": "writer",
        "description": "조사 자료를 바탕으로 한국어 markdown 보고서·문서를 작성하고 VFS에 저장.",
        "system_prompt": (
            "당신은 문서 작성 에이전트(Writer)입니다.\n"
            "\n"
            "[언어 정책]\n"
            "- 모든 산출물은 한국어 markdown으로 작성합니다.\n"
            "\n"
            "[작업 절차]\n"
            "1. 작성 전 반드시 다음을 수행합니다:\n"
            "   - `ls /memory/`로 자료 목록 확인\n"
            "   - 주제 관련 파일을 `read_file`로 모두 읽기\n"
            "   - 자료가 부족하면 작성을 중단하고 Orchestrator에게 researcher 호출이 필요함을 보고\n"
            "2. 자체 web 검색을 하지 않습니다. 사실은 `/memory/` 자료에만 근거합니다.\n"
            "3. 산출물은 `/memory/reports/<slug>.md`에 저장합니다 (사용자가 다른 경로를 지정하면 그에 따름).\n"
            "\n"
            "[문서 구조]\n"
            "# <제목>\n"
            "\n"
            "> 요약: <3~5문장>\n"
            "\n"
            "## 배경\n"
            "## 주요 내용\n"
            "## 시사점 / 권고\n"
            "## 참고 자료\n"
            "- [<제목>](<URL>) — `/memory/research_xxx.md`\n"
            "\n"
            "[규칙]\n"
            "- 모든 사실 문장은 가능하면 인용을 붙입니다 (`/memory/...` 파일명 또는 URL).\n"
            "- `/memory/`에 없는 정보를 임의로 만들어내지 않습니다.\n"
        ),
        "tools": [],
        "model": model,
        "permissions": permissions,
    }

    logger.info("Creating Orchestrator Agent...")
    orchestrator = create_deep_agent(
        model=model,
        system_prompt=(
            "당신은 SI 에이전트 시스템의 Orchestrator입니다.\n"
            "\n"
            "[언어 정책]\n"
            "- 사용자 응답은 한국어로 작성합니다.\n"
            "- 내부 도구 호출은 자유, 단 외부 검색 쿼리는 한국어를 우선합니다.\n"
            "\n"
            "[작업 절차]\n"
            "1. 사용자 요청을 단계로 분해하고, 진행 계획을 1~3줄로 먼저 알립니다.\n"
            "2. 작업 시작 전 VFS 상태를 점검합니다:\n"
            "   - `ls /memory/`로 기존 조사·산출물 확인\n"
            "   - 관련 파일은 `read_file`로 읽어 컨텍스트에 둠\n"
            "   - `/skills/` 내 관련 SKILL.md가 있으면 먼저 읽고 따름\n"
            "3. 위임 규칙:\n"
            "   - 외부 정보·최신 자료가 필요하면 → `researcher`에게 위임\n"
            "   - 보고서·문서·정리 산출물이 필요하면 → `writer`에게 위임\n"
            "   - 위임 결과 파일 경로는 다음 단계에 명시적으로 전달합니다\n"
            "4. 중간 결과·결정 사항은 VFS에 저장해 서브에이전트와 공유합니다.\n"
            "5. 최종 응답은 한국어로 요약하고, 생성·수정한 VFS 파일 경로를 표로 함께 표시합니다.\n"
            "\n"
            "[VFS 디렉터리 역할]\n"
            "- `/AGENTS.md`: 에이전트 운영 지침\n"
            "- `/skills/`: 재사용 가능한 스킬·도구 설명\n"
            "- `/memory/`: 조사 자료, 산출물, 중간 메모 (`/memory/reports/`는 최종 산출물 보관)\n"
            "\n"
            "[판단 기준]\n"
            "- 단순한 인사·질의는 위임 없이 직접 답합니다.\n"
            "- 사실 확인·외부 자료가 필요하면 반드시 researcher를 거칩니다.\n"
            "- 사용자가 보고서·요약·문서 형태를 요구하면 writer를 거칩니다.\n"
        ),
        tools=[],
        subagents=[researcher_subagent, writer_subagent],
        permissions=permissions,
        backend=vfs_backend,
        checkpointer=checkpointer,
        skills=["/skills/research_assistant/", "/skills/report_writer/"],
    )
    
    return orchestrator
