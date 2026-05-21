# SI Agent Scaffolding Project (에이전트 구축 스캐폴딩)

본 프로젝트는 SI 사업에서 복잡한 업무를 수행하는 AI Agent 시스템을 구축하기 위한 기본적인 스캐폴딩(Scaffolding) 템플릿입니다. `deepagents` 프레임워크를 기반으로 하며, PostgreSQL을 사용한 대화 이력 관리(Thread Saver) 및 가상 파일 시스템(VFS) 저장소를 포함하고 있습니다.

---

## 주요 기능
1. **오케스트라 & 서브 에이전트 아키텍처**: 메인 코디네이터 에이전트와 분야별 전문 서브 에이전트(`researcher`, `writer`) 협업 구조.
2. **Postgres VFS**: 에이전트가 사용하는 스페이스 파일(AGENTS.md, skills, memory 등)을 Postgres 데이터베이스 내에 가상 파일 시스템 형태로 격리 보존.
3. **Agent + Admin UI**: 에이전트와의 실시간 채팅(ChatView) 및 VFS 내 파일/폴더를 시각적으로 확인하고 직접 편집 가능한 관리자 대시보드(AdminView) 제공.
4. **Opik 통합**: LLM 모니터링 및 트레이싱을 위해 Comet Opik SDK를 통합하여 관찰 가능성(observability) 확보.

---

## 개발 환경 설정 (Phase 1 Quickstart)

### 사전 필수 환경
- Python `3.12+`
- Node.js `20+`
- PostgreSQL 데이터베이스 실행 중

### 1. 백엔드 실행 (`server/`)
```bash
cd server
# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열고 데이터베이스 주소, OpenAI, Opik API 키 등을 설정합니다.

# 서버 기동 (Port 8000)
uv run python main.py
```

### 2. 프론트엔드 실행 (`client/`)
```bash
cd client
# 의존성 설치
npm install

# 개발 서버 실행 (Port 5173)
npm run dev
```

### 3. 접속 주소
- Frontend UI: `http://localhost:5173`
- Backend API Docs: `http://localhost:8000/docs`
