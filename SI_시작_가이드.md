# SI 프로젝트 인력을 위한 시작 가이드

이 문서는 **AI 에이전트를 처음 다루는 SI 프로젝트 인력**이 이 저장소를 이해하고, 로컬에서 실행해 본 뒤, **실제 고객·납품 프로젝트에 어떻게 가져가야 하는지**를 단계별로 설명합니다.

개발 세부 사항이 필요하면 함께 읽을 문서:


| 문서                                   | 용도                    |
| ------------------------------------ | --------------------- |
| [README.md](./README.md)             | 기능 요약·Quickstart      |
| [AGENTS.md](./AGENTS.md)             | 에이전트 역할·VFS 운영 규칙(필수) |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | API·DB·불변 규칙          |
| [deploy/SETUP.md](./deploy/SETUP.md) | Kubernetes 배포         |
| [ROADMAP.md](./ROADMAP.md)           | 마일스톤·미완료 항목           |


---

## 1. 이 프로젝트는 무엇인가?

**한 줄 요약:** SI 현장에서 “조사 → 보고서 작성” 같은 반복 업무를 **여러 AI 에이전트가 협업**하도록 만든 **시작 템플릿(스캐폴딩)** 입니다. 완성된 제품이 아니라, **복사·수정해서 고객 도메인에 맞게 키우는 뼈대**입니다.

### 비유로 이해하기


| 일반 SI 프로젝트     | 이 템플릿에서 대응하는 것                                                                                        |
| -------------- | ----------------------------------------------------------------------------------------------------- |
| 업무 매뉴얼·표준 절차서  | 루트 `AGENTS.md` (에이전트 운영 규칙)                                                                           |
| 공유 드라이브·산출물 폴더 | Postgres **VFS**(가상 파일 시스템)의 `/memory/`, `/skills/`                                                   |
| PM·리드가 일을 나눔   | **Orchestrator** (메인 에이전트)                                                                            |
| 조사 담당          | **researcher** 서브 에이전트 (웹 검색 → `/memory/` 저장)                                                         |
| 문서 작성 담당       | **writer** 서브 에이전트 (`/memory/`만 보고 보고서 작성)                                                            |
| 도메인 전담 (실 SI)  | **추가 SubAgent** — 예: `meeting_scheduler`, `consultation_lookup` ([6.5절](#651-설계-원칙--기능이-아니라-역할로-쪼개기)) |
| 사용자 화면         | `client/` React UI (채팅 + VFS 관리자)                                                                     |
| 서버·API         | `server/` FastAPI + LangGraph + `deepagents`                                                          |


### 기술 스택 (알아두면 좋은 이름만)

- **백엔드:** Python 3.12+, FastAPI, LangGraph, `deepagents`
- **프론트:** React (Vite), TypeScript
- **저장소:** PostgreSQL (대화 이력 + VFS 파일 전부)
- **LLM:** OpenAI / Anthropic / Gemini 중 `.env`로 선택
- **웹 검색:** 네이버 검색 Open API (`researcher`용)
- **관측(선택):** Comet Opik or DidimLLMOps (LLM 호출 추적)

---

## 2. 폴더 구조 — 어디를 손대면 되나?

```
agent-template/
├── SI_시작_가이드.md    ← 지금 읽는 문서
├── AGENTS.md            ← 에이전트 규칙 (디스크 ↔ VFS 동기화 대상)
├── README.md
├── client/              ← UI (채팅, VFS 트리·에디터)
├── server/              ← API, 에이전트, VFS, DB 초기화
│   ├── .env.example     ← 환경 변수 샘플
│   └── app/agent.py     ← 서브에이전트·프롬프트 정의
├── deploy/              ← K8s 배포 매니페스트
└── mcp/                 ← MCP 연동 설계 (Phase 3, 템플릿 단계)
```

**초보자가 자주 수정하는 위치**

1. `**AGENTS.md`** — 팀 운영 규칙, 언어 정책, VFS 경로 규칙
2. `**server/app/agent.py**` — 서브에이전트 설명·시스템 프롬프트·도구 연결
3. `**server/app/tools.py**` — 고객사 API·DB 조회 등 **새 도구** 추가
4. **Admin UI 또는 VFS API** — `/skills/` 아래 `SKILL.md` (재사용 절차)
5. `**server/.env`** — DB URL, API 키, 모델 선택 (커밋 금지)

---

## 3. 설치하기 (로컬 개발)

### 3.1 사전 준비


| 항목              | 권장 버전   | 확인 방법                                                   |
| --------------- | ------- | ------------------------------------------------------- |
| Python          | 3.12 이상 | `python3 --version`                                     |
| Node.js         | 20 이상   | `node --version`                                        |
| PostgreSQL      | 15 이상   | DB 접속 가능 여부                                             |
| uv (Python 패키지) | 최신      | `uv --version` (없으면 [uv 설치](https://docs.astral.sh/uv/) |
| Git             | —       | 저장소 clone 완료                                            |


**API 키 (최소)**

- **LLM:** OpenAI / Anthropic / Gemini 중 하나 (`.env`의 `DEEPAGENT_MODEL_`*)
- **웹 검색:** [네이버 개발자 센터](https://developers.naver.com/apps/#/list)에서 애플리케이션 등록 후 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`

**PostgreSQL 준비 예시 (로컬 Docker)**

```bash
docker run -d --name si-agent-pg \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16
```

회사 환경에서는 이미 있는 DB URL을 받아 `DATABASE_URL`에 넣으면 됩니다.

### 3.2 백엔드 (`server/`)

```bash
cd server
uv sync
cp .env.example .env
```

`.env`를 열어 최소한 아래를 채웁니다.

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
DEEPAGENT_MODEL_PROVIDER=openai
DEEPAGENT_MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
```

서버 기동:

```bash
uv run python main.py
```

- API 문서: [http://localhost:8000/docs](http://localhost:8000/docs)  
- 최초 기동 시 `init_db()`가 **VFS 테이블·LangGraph 체크포인트 테이블**을 만들고, VFS가 비어 있으면 `AGENTS.md`와 기본 `/skills/`, `/memory/`를 **시드**합니다.

### 3.3 프론트엔드 (`client/`)

```bash
cd client
npm install
npm run dev
```

브라우저: [http://localhost:5173](http://localhost:5173)

- **Chat:** 에이전트와 대화 (조사·보고서 요청 테스트)
- **Admin:** VFS 파일 트리 보기·직접 편집

### 3.4 VS Code로 한 번에 띄우기 (선택)

`.vscode/launch.json`에 **Full Stack** 구성이 있습니다. Server 실행 전 PostgreSQL port-forward 태스크가 있으므로, **회사 K8s DB를 쓰는 경우** `.vscode/tasks.json`의 네임스페이스·서비스 이름을 팀 환경에 맞게 수정해야 합니다.

---

## 4. 설치 후 반드시 해볼 확인

1. **헬스·상태**
  브라우저 또는 `curl`로 `GET http://localhost:8000/api/status` — DB·Opik 설정 여부 확인.
2. **VFS 시드 확인**
  Admin UI에서 `/AGENTS.md`, `/skills/`, `/memory/`가 보이는지 확인.
3. **간단한 업무 시나리오**
  채팅에 예: *「2025년 국내 SI 시장 동향을 조사하고 요약 보고서를 작성해줘」*  
  - researcher → `/memory/research_*.md`  
  - writer → `/memory/reports/*.md`  
   경로에 파일이 생기는지 Admin에서 확인.
4. **네이버 API 미설정 시**
  researcher가 검색에 실패합니다. `.env`의 네이버 키를 다시 확인하세요.

---

## 5. 주의사항 (꼭 읽을 것)

### 5.1 보안·운영


| 주의               | 설명                                                                                                    |
| ---------------- | ----------------------------------------------------------------------------------------------------- |
| `**.env` 커밋 금지** | API 키·DB 비밀번호 유출 방지. `.gitignore` 유지.                                                                 |
| **인증 미구현**       | 현재 템플릿은 **인증이 기본 포함되지 않음** ([ROADMAP.md](./ROADMAP.md)). 내부망·VPN 뒤에서만 쓰거나, SI 프로젝트에서 JWT/SSO를 추가해야 함. |
| **LLM 비용**       | 모든 대화·서브에이전트 호출이 과금됩니다. 테스트 시 짧은 프롬프트·저렴한 모델 사용 권장.                                                   |
| **외부 검색 데이터**    | 네이버 검색 결과·URL은 고객사 **개인정보·저작권 정책**에 맞게 사용·보관.                                                         |


### 5.2 아키텍처 불변 규칙 ([ARCHITECTURE.md](./ARCHITECTURE.md))

1. **서버 디스크에 업무 산출물을 쌓지 않음** — 조사·보고서·스킬은 **Postgres VFS** (`/memory/`, `/skills/` 등)에만 저장.
2. **VFS 경로는 반드시 `/`로 시작** — 예: `/memory/research_topic.md` (상대 경로 사용 금지).
3. **에이전트 API는 JSON-RPC** — HTTP 상태는 200이고, 오류는 JSON body에 담김.
4. `**AGENTS.md` 이중 관리** — 디스크의 `AGENTS.md`는 시드 원본. 운영 중 Admin에서 VFS `/AGENTS.md`를 수정했다면, **팀 규칙에 맞게 디스크와 동기화**할지 정해야 함 (재시드 시 덮어쓰기 주의).

### 5.3 에이전트 역할 분리 ([AGENTS.md](./AGENTS.md))

- **researcher:** 사실·URL·원자료만. 해석·결론 금지.  
- **writer:** `/memory/`만 근거. **자체 웹 검색 금지.** 자료 없으면 작성 중단 후 orchestrator에 보고.  
- **Orchestrator:** 위임·VFS 저장·최종 한국어 응답.

역할을 섞으면 환각·출처 누락이 늘어납니다.

### 5.4 DB·VFS 초기화

```bash
cd server
uv run python scripts/reseed_vfs.py
```

- **모든 VFS 파일을 삭제**하고 `AGENTS.md`·기본 스킬을 다시 넣습니다.  
- **운영 DB에서는 실행하지 마세요.** 개발·데모 DB 전용.

### 5.5 Opik (선택)

`OPIK_API_KEY`가 없으면 트레이싱 없이 동작합니다. PoC 단계에서는 생략 가능, **운영·품질 분석** 단계에서 연동을 권장합니다.

---

## 6. 실 SI 프로젝트에 적용하는 방법

아래는 **고객 프로젝트에 이 템플릿을 가져갈 때** 권장하는 순서입니다. “코드만 배포”가 아니라 **업무 규칙·산출물 구조**를 먼저 맞추는 것이 성공 확률을 높입니다.

### 6.1 0단계 — 범위 정하기 (1~2일)


| 질문               | 예시                                     |
| ---------------- | -------------------------------------- |
| 자동화할 업무는?        | RFP 조사, 규정 Q&A, 장애 보고서 초안, 코드 리뷰 요약    |
| 사람이 반드시 검증할 단계는? | 최종 보고서 승인, 대외 발송                       |
| 데이터는 어디까지 허용?    | 공개 웹만 / 사내 Wiki / 고객 DB (→ 별도 도구·망 분리) |


**PoC는 한 가지 시나리오만** (예: “주제 조사 + 3페이지 요약 보고서”) 고르세요.

### 6.2 1단계 — 저장소·환경 분리

1. 이 템플릿을 **고객·프로젝트 전용 저장소**로 fork 또는 복사.
2. `server/.env`는 **환경별** (local / dev / prod) 분리, Secret Manager·K8s Secret 사용 ([deploy/SETUP.md](./deploy/SETUP.md)).
3. PostgreSQL은 **프로젝트 전용 DB** 또는 스키마 분리 (VFS + 대화 이력이 같은 DB에 쌓임).

### 6.3 2단계 — `AGENTS.md`를 “프로젝트 표준”으로 재작성

디스크 `AGENTS.md`를 고객사에 맞게 수정한 뒤:

- 신규 환경: 서버 최초 기동 시 VFS에 자동 시드됨.  
- 이미 DB가 있는 환경: Admin에서 `/AGENTS.md`를 수동 반영하거나, 개발 DB에서만 `reseed_vfs.py` 사용.

**반드시 적을 내용 예시**

- 응답 언어 (한국어/영문 혼용 규칙)  
- `/memory/` 하위 폴더 규칙 (예: `/memory/rfp/`, `/memory/incidents/`)  
- 금지 사항 (개인정보 입력 금지, 추측 금지, 출처 필수)  
- 승인 워크플로 (writer 산출물은 “초안”임을 명시)

### 6.4 3단계 — 스킬(`SKILL.md`)로 도메인 절차 고정

**맞습니다. SubAgent를 늘리면 스킬도 함께 늘어나는 경우가 대부분입니다.**  
스킬은 “그 SubAgent가 매번 따라야 할 절차서”이고, SubAgent는 “그 절차를 실행하는 실행 주체”입니다. [6.5절](#65-4단계--서브에이전트도구-확장-serverappagentpy-toolspy)에서 에이전트·도구를 추가할 때, **같은 단계에서 스킬 디렉터리도 추가**하는 것이 맞습니다.

#### SubAgent ↔ 스킬 관계

| 구성 요소 | 역할 | SubAgent 확장 시 |
|-----------|------|------------------|
| `SubAgent` (`agent.py`) | 누가 실행하는지, 어떤 **도구**를 쓰는지 | `meeting_scheduler` 등 정의 추가 |
| `/skills/<이름>/SKILL.md` (VFS) | **어떻게** 할지(체크리스트, 경로, 금지) | 역할마다 폴더 추가 (또는 기존 스킬 보강) |
| `skills=[...]` (`create_deep_agent`) | Orchestrator·서브가 **자동으로 참조할 스킬 경로** | 새 `/skills/.../` 경로 등록 |
| `AGENTS.md` | Orchestrator **위임 표** + “관련 SKILL 먼저 읽기” | 위임 대상·스킬 경로 동기화 |

템플릿 기본 매핑:

| SubAgent | 스킬 경로 |
|----------|-----------|
| `researcher` | `/skills/research_assistant/` |
| `writer` | `/skills/report_writer/` |

실 SI 확장 예 ([6.5.2](#652-vfs스킬-디렉터리-설계-회의--상담)):

| SubAgent | 스킬 경로 |
|----------|-----------|
| `meeting_scheduler` | `/skills/meeting_scheduler/` |
| `meeting_minutes_writer` | `/skills/meeting_minutes/` |
| `consultation_lookup` | `/skills/consultation_lookup/` |
| `consultation_register` | `/skills/consultation_register/` |

**1 SubAgent : 1 스킬 폴더**를 기본으로 하되, 역할이 거의 같으면 하나의 `SKILL.md`를 공유할 수 있습니다. 반대로 **한 SubAgent에 스킬을 안 붙이면** 프롬프트만으로 동작해 팀마다 결과 편차가 커집니다.

#### 스킬 문서에 넣을 내용 (역할별)

`/skills/<도메인>/SKILL.md` 상단 메타데이터 예:

```markdown
---
name: Meeting Scheduler
description: 회의·회의실 예약 절차
allowed_tools: [reserve_meeting, ls, read_file, write_file, edit_file]
---
```

본문에는 최소한 아래를 적습니다.

- 시작 전 체크리스트 (필수 입력값)  
- 호출할 도구 순서  
- VFS 저장 경로·파일명 규칙 (예: `/memory/meetings/schedule_<slug>.md`)  
- **금지** (다른 SubAgent 몫 — 예: 회의록 본문 작성 금지)  
- Human-in-the-loop (CRM 등록 전 사용자 확인 등)

#### 함께 수정해야 하는 파일 (체크리스트)

SubAgent를 하나 추가할 때 보통 **네 곳**이 맞물립니다.

1. **VFS** — Admin 또는 시드로 `/skills/<새역할>/SKILL.md` 생성  
2. **`server/app/agent.py`** — `SubAgent` 정의 + `skills=[...]`에 경로 추가  
3. **`AGENTS.md`** — 위임 규칙·해당 스킬 경로 명시  
4. **`server/app/database.py`** (선택) — 최초 DB 시드에 새 스킬을 넣을 때만. 이미 운영 중이면 Admin 업로드로 충분  

`system_prompt`에 “`/skills/meeting_scheduler/SKILL.md`를 먼저 읽어라”고 적어 두면, 스킬 파일과 SubAgent가 **이름으로 연결**됩니다.

#### 예시 (RFP가 아닌 회의 도메인)

`/skills/meeting_scheduler/SKILL.md` — 예약 API 호출 전 시간·참석자·룸 ID 확인, 성공 시 `/memory/meetings/schedule_*.md` 저장.

---

### 6.5 4단계 — 서브에이전트·도구 확장 (`server/app/agent.py`, `tools.py`)

템플릿 기본은 `researcher` + `writer` 두 개입니다. **실 SI 프로젝트**에서는 업무 도메인마다 SubAgent가 늘어나며, [6.4절](#64-3단계--스킬skillmd로-도메인-절차-고정)의 **스킬도 같은 비율로 추가**하는 것이 일반적입니다. (예: 회의 예약·회의록, 상담·고객 조회·결과 등록)


| 필요 시         | 작업                                                             |
| ------------ | -------------------------------------------------------------- |
| 사내 API·DB 조회 | `tools.py`에 `@tool` 함수 추가 → **해당 업무만** 담당하는 SubAgent에만 연결      |
| 역할 추가        | `agent.py`에 `SubAgent` 정의 + `AGENTS.md` 위임 규칙·`description` 갱신 |
| 검색 엔진 변경     | `tools.py`의 `web_search` 구현 교체 (네이버 → 사내 검색 API)               |


**원칙 (템플릿 확장 시에도 유지)**

1. **한 SubAgent = 한 책임** — “회의 전부”가 아니라 `meeting_scheduler` / `meeting_minutes_writer`처럼 쪼갠다.
2. **도구는 최소 권한** — 고객 DB 조회 도구는 `consultation_lookup`에만, 등록은 `consultation_register`에만.
3. **Orchestrator는 라우터** — 직접 API를 호출하지 않고, 단계 분해 후 SubAgent에 위임.
4. **VFS로 handoff** — SubAgent 간 컨텍스트는 `/memory/<도메인>/` 파일 경로로 넘긴다.

아래 **6.5.1~6.5.4**는 회의·상담 도메인을 예로 든 **실무 적용 설계서**입니다. 코드는 프로젝트마다 다르지만, 수정 위치와 판단 기준은 동일합니다.

---

### 6.5.1 설계 원칙 — “기능”이 아니라 “역할”로 쪼개기

잘못된 예: `meeting_agent` 하나에 예약 API + 회의록 작성 + 메일 발송을 모두 넣기  
→ 도구·프롬프트가 비대해지고, 잘못된 API 호출·환각이 늘어납니다.

권장 예: 업무 단계·**쓰기/읽기 권한**이 다른 일을 SubAgent로 분리합니다.

```mermaid
flowchart TB
  User([사용자]) --> Orch[Orchestrator]
  Orch --> R[researcher]
  Orch --> W[writer]
  Orch --> MS[meeting_scheduler]
  Orch --> MM[meeting_minutes_writer]
  Orch --> CL[consultation_lookup]
  Orch --> CR[consultation_register]
  MS --> CalAPI[(일정/회의실 API)]
  CL --> CRM[(고객/상담 API)]
  CR --> CRM
  MS --> VFS[(VFS /memory/meetings/)]
  MM --> VFS
  CL --> VFS
  CR --> VFS
  W --> VFS
  R --> VFS
```




| SubAgent                 | 책임              | 연결 도구 (예)                                   | VFS 산출물 (예)                             |
| ------------------------ | --------------- | ------------------------------------------- | --------------------------------------- |
| `researcher`             | 공개·외부 자료 조사     | `web_search`                                | `/memory/research_*.md`                 |
| `writer`                 | 조사·중간 메모 기반 문서  | (없음, VFS만)                                  | `/memory/reports/*.md`                  |
| `meeting_scheduler`      | 회의·룸 예약, 참석자 확인 | `reserve_meeting`, `list_room_availability` | `/memory/meetings/schedule_*.md`        |
| `meeting_minutes_writer` | 회의록·액션아이템 초안    | (없음)                                        | `/memory/meetings/minutes_*.md`         |
| `consultation_lookup`    | 고객·이력 **조회만**   | `get_customer`, `list_consultations`        | `/memory/consultations/lookup_*.md`     |
| `consultation_register`  | 상담 결과 **등록만**   | `register_consultation_result`              | `/memory/consultations/registered_*.md` |


템플릿의 `researcher` / `writer`는 **범용**으로 두고 (불 필요 시 삭제), 고객 도메인 SubAgent를 **추가**하는 방식이 가장 안전합니다.

---

### 6.5.2 VFS·스킬 디렉터리 설계 (회의 / 상담)

도메인별로 `/memory/`·`/skills/`를 나누면 Orchestrator가 “어디를 보라”고 지시하기 쉽습니다.

```txt
/skills/
├── research_assistant/     # (템플릿 기본) 조사
├── report_writer/          # (템플릿 기본) 보고서
├── meeting_scheduler/      # 예약 절차·필수 확인 항목
├── meeting_minutes/        # 회의록 포맷·액션아이템 규칙
├── consultation_lookup/    # 조회 전 개인정보·마스킹 규칙
└── consultation_register/  # 등록 필수 필드·승인 전 초안 규칙

/memory/
├── research_*.md           # (기존) 외부 조사
├── reports/                # (기존) 최종 보고서
├── meetings/
│   ├── schedule_<slug>.md    # 예약 결과·회의 ID
│   └── minutes_<slug>.md       # 회의록 초안
└── consultations/
    ├── lookup_<slug>.md        # 조회 스냅샷 (마스킹된 요약)
    └── registered_<slug>.md    # 등록 요청·확인용 초안
```

**스킬 예시** (`/skills/meeting_scheduler/SKILL.md` 요지):

- 예약 전: 회의 제목, 시작·종료, 참석자, 회의실/화상 링크 요구사항 확인  
- `reserve_meeting` 호출 후 반드시 `/memory/meetings/schedule_<slug>.md` 저장  
- 회의록 작성은 하지 않음 → 필요 시 Orchestrator가 `meeting_minutes_writer`에 위임

---

### 6.5.3 `AGENTS.md` 위임 규칙 확장 (Orchestrator가 읽는 표)

디스크 `AGENTS.md`의 Orchestrator 절에 **위임 표**를 추가합니다. VFS `/AGENTS.md`와 동기화하세요.

```markdown
## 위임 규칙 (확장)

| 사용자 요청 유형 | 위임 SubAgent | 선행 조건 |
|------------------|---------------|-----------|
| 웹·시장·규정 등 외부 조사 | researcher | — |
| 보고서·제안서·긴 문서 | writer | 관련 `/memory/research_*.md` 또는 도메인 메모 존재 |
| 회의·룸 예약, 일정 조율 | meeting_scheduler | `/skills/meeting_scheduler/SKILL.md` 확인 |
| 회의록·액션아이템 정리 | meeting_minutes_writer | `/memory/meetings/schedule_*.md` 또는 사용자가 제공한 메모 |
| 고객 정보·상담 이력 조회 | consultation_lookup | 고객 식별자(ID/전화 뒷자리 등) 확보, 조회 목적 명시 |
| 상담 결과·후속 조치 등록 | consultation_register | `lookup_*.md` 존재 또는 조회 SubAgent 완료 후 |

## 금지
- consultation_lookup이 상담 결과를 등록하지 않음
- consultation_register가 조회 없이 고객 정보를 추측하지 않음
- meeting_scheduler가 회의록 본문을 장문으로 작성하지 않음 (요약·메타만)
```

---

### 6.5.4 코드 적용 예시 (`tools.py` + `agent.py`)

아래는 **설명용 스켈레톤**입니다. 실제 API URL·스키마는 고객사 연동 명세에 맞게 구현합니다.

#### (1) 도구 정의 — 읽기/쓰기 분리 (`server/app/tools.py`)

```python
from langchain_core.tools import tool

@tool
def reserve_meeting(title: str, start_at: str, end_at: str, attendee_ids: str, room_id: str) -> str:
    """사내 일정 API로 회의를 예약하고 meeting_id를 반환합니다."""
    # ... HTTP 호출 ...
    return "meeting_id=M-20260522-001; status=confirmed"

@tool
def get_customer(customer_id: str) -> str:
    """CRM에서 고객 기본 정보·마스킹된 식별 정보만 조회합니다. 등록/수정 없음."""
    # ... HTTP 호출 ...
    return "customer_id=C-1001; name=홍**; tier=gold; ..."

@tool
def register_consultation_result(customer_id: str, summary: str, next_action: str) -> str:
    """상담 결과를 CRM에 등록합니다. 조회 전용 도구와 분리합니다."""
    # ... HTTP 호출 ...
    return "consultation_id=CS-9001; status=registered"
```

#### (2) SubAgent 등록 (`server/app/agent.py`)

`description`은 Orchestrator가 **위임 대상을 고를 때** 가장 많이 보는 필드입니다. “언제 부르면 되는지”를 한국어로 명확히 적습니다.

```python
meeting_scheduler_subagent: SubAgent = {
    "name": "meeting_scheduler",
    "description": "회의·회의실 예약, 참석자 일정 확인. 결과는 /memory/meetings/schedule_*.md 에 저장.",
    "system_prompt": (
        "당신은 회의 예약 전담 에이전트입니다.\n"
        "1. /skills/meeting_scheduler/SKILL.md 를 먼저 읽습니다.\n"
        "2. 필수 정보가 부족하면 예약 API를 호출하지 않고 Orchestrator에 요청합니다.\n"
        "3. reserve_meeting 성공 후 schedule_<slug>.md 를 VFS에 저장합니다.\n"
        "4. 회의록 본문 작성은 하지 않습니다.\n"
    ),
    "tools": [reserve_meeting],  # list_room_availability 등 추가 가능
    "model": model,
    "permissions": permissions,
}

meeting_minutes_writer_subagent: SubAgent = {
    "name": "meeting_minutes_writer",
    "description": "회의록·액션아이템 초안 작성. /memory/meetings/ 의 schedule·메모만 근거.",
    "system_prompt": "… /skills/meeting_minutes/SKILL.md … web_search·reserve_meeting 금지 …",
    "tools": [],  # VFS read/write만
    "model": model,
    "permissions": permissions,
}

consultation_lookup_subagent: SubAgent = {
    "name": "consultation_lookup",
    "description": "고객·상담 이력 조회만. 결과는 /memory/consultations/lookup_*.md",
    "system_prompt": "… /skills/consultation_lookup/SKILL.md … 등록 API 호출 금지 …",
    "tools": [get_customer],  # list_consultations 등
    "model": model,
    "permissions": permissions,
}

consultation_register_subagent: SubAgent = {
    "name": "consultation_register",
    "description": "상담 결과·후속조치를 CRM에 등록. 반드시 lookup 자료 또는 명시된 customer_id 필요.",
    "system_prompt": (
        "당신은 상담 결과 등록 전담 에이전트입니다.\n"
        "1. /skills/consultation_register/SKILL.md 를 따릅니다.\n"
        "2. /memory/consultations/lookup_*.md 가 없으면 등록을 중단하고 조회 선행을 보고합니다.\n"
        "3. register_consultation_result 후 registered_<slug>.md 를 저장합니다.\n"
        "4. 고객 정보를 추측하거나 조회 도구를 호출하지 않습니다.\n"
    ),
    "tools": [register_consultation_result],
    "model": model,
    "permissions": permissions,
}

# create_deep_agent(...) 호출 시:
subagents=[
    researcher_subagent,
    writer_subagent,
    meeting_scheduler_subagent,
    meeting_minutes_writer_subagent,
    consultation_lookup_subagent,
    consultation_register_subagent,
],
skills=[
    "/skills/research_assistant/",
    "/skills/report_writer/",
    "/skills/meeting_scheduler/",
    "/skills/meeting_minutes/",
    "/skills/consultation_lookup/",
    "/skills/consultation_register/",
],
```

Orchestrator `system_prompt`의 위임 규칙도 같은 목록으로 맞춥니다 (`agent.py` 166~169행 부근).

---

### 6.5.5 사용자 요청 → 실행 흐름 예시

#### 예시 A — “내일 14시에 김대리·이과장이랑 화상 회의 잡고, 오늘 킥오프 회의록 초안 써줘”


| 단계  | 담당                       | 동작                                                                                         |
| --- | ------------------------ | ------------------------------------------------------------------------------------------ |
| 1   | Orchestrator             | 요청을 **예약** / **회의록** 두 갈래로 분해, 계획 1~3줄 공지                                                  |
| 2   | `meeting_scheduler`      | SKILL 확인 → 시간·참석자 확인 → `reserve_meeting` → `/memory/meetings/schedule_kickoff_20260522.md` |
| 3   | `meeting_minutes_writer` | 사용자가 준 킥오프 메모 또는 VFS 기존 메모 `read_file` → `/memory/meetings/minutes_kickoff_20260522.md`    |
| 4   | Orchestrator             | 최종 응답 + 생성 파일 경로 표 (회의 ID, 회의록 경로)                                                         |


회의록 SubAgent에게 **예약 API 도구를 주지 않는** 이유: 회의록 작성 중 잘못된 예약 변경을 막기 위함입니다.

#### 예시 B — “고객 C-1001 상담 이력 보고, 오늘 통화 내용 CRM에 등록해줘”


| 단계  | 담당                      | 동작                                                                                                  |
| --- | ----------------------- | --------------------------------------------------------------------------------------------------- |
| 1   | Orchestrator            | **조회 → 등록** 순서 고정 (등록만 먼저 하지 않음)                                                                    |
| 2   | `consultation_lookup`   | `get_customer`, `list_consultations` → `/memory/consultations/lookup_c1001_20260522.md` (마스킹·출처 명시) |
| 3   | Orchestrator            | 사용자에게 통화 요약·등록 필드 확인 (Human-in-the-loop, 선택)                                                        |
| 4   | `consultation_register` | lookup 파일 `read_file` 후 `register_consultation_result` → `registered_*.md`                          |
| 5   | Orchestrator            | 등록 ID·VFS 경로 안내                                                                                     |


**조회와 등록을 한 SubAgent에 합치지 않는** 이유: LLM이 “조회만 하라”는 상황에서도 등록 API를 호출하는 사고를 줄이기 위함입니다. (최소 권한·감사 추적에도 유리)

#### 예시 C — 템플릿 기본 역할과 함께 쓰기

“경쟁사 A사 최근 뉴스 조사하고, 다음 주 고객 미팅 안건으로 보고서 만들어줘”

1. `researcher` → `/memory/research_competitor_a.md`
2. `meeting_scheduler` → 미팅 예약 (안건은 schedule 파일에 링크)
3. `writer` → research + schedule 메타를 인용해 `/memory/reports/client_meeting_brief.md`

---

### 6.5.6 적용 체크리스트 (실 SI 인수 시)


| #   | 확인 항목                                                                   |
| --- | ----------------------------------------------------------------------- |
| 1   | SubAgent 이름·`description`이 Orchestrator 위임 표와 일치하는가                     |
| 2   | 각 SubAgent `tools` 목록에 **불필요한 API**가 없는가                                |
| 3   | `/skills/<역할>/SKILL.md`가 VFS에 시드·배포되었는가 (`database.py` 시드 또는 Admin 업로드) |
| 4   | `/memory/<도메인>/` 경로 규칙이 `AGENTS.md`에 문서화되었는가                            |
| 5   | 개인정보·CRM 등록은 **승인 전 초안** 문구가 writer·register 스킬에 있는가                    |
| 6   | PoC는 **한 도메인·한 시나리오**부터 (예: 상담 조회만 → 이후 등록 추가)                          |


SubAgent가 6개 이상이면 `agent.py`가 길어집니다. 팀 규모가 크면 `server/app/subagents/meeting.py`처럼 **파일 분리**만 하고, `create_agent_system()`에서 import해 `subagents=[...]`로 합치면 됩니다.

---

### 6.6 5단계 — UI·API 연동

- **내부 PoC:** 기본 `client/` Chat + Admin으로 충분.  
- **고객 포털 임베딩:** `POST /api/rpc` (JSON-RPC), SSE 스트리밍 등 [ARCHITECTURE.md](./ARCHITECTURE.md) 계약에 맞춰 기존 포털에서 호출.  
- **Cursor·IDE 연동:** [mcp/DESIGN.md](./mcp/DESIGN.md) 방향으로 MCP 서버 분리 (Phase 3).

### 6.7 6단계 — 배포·관측

1. [deploy/dependencies.md](./deploy/dependencies.md) 선행 조건 충족.
2. [deploy/SETUP.md](./deploy/SETUP.md)대로 Secret·Kustomize 적용.
3. Opik·로그로 **프롬프트·토큰·실패율** 모니터링.
4. CI: [.github/workflows/ci.yml](./.github/workflows/ci.yml) 참고해 팀 파이프라인에 연결.

### 6.8 7단계 — 운영·거버넌스

- **Human-in-the-loop:** writer 산출물은 “승인 전 초안”으로 라벨링.  
- **주기적 VFS 정리:** 오래된 `/memory/research_*.md` 아카이브 정책.  
- **모델·프롬프트 변경 이력:** Git으로 `AGENTS.md`, `agent.py` 버전 관리.  
- **장애 시:** DB 연결, API 키 만료, 네이버 API 쿼터, LLM rate limit 순으로 점검.

---

## 7. 자주 겪는 문제


| 증상                 | 점검                                                                       |
| ------------------ | ------------------------------------------------------------------------ |
| 서버 기동 실패           | `DATABASE_URL` 접속 가능 여부, Postgres 실행 여부                                  |
| 채팅은 되는데 검색 안 됨     | `NAVER_CLIENT_ID` / `SECRET`                                             |
| VFS가 비어 있음         | 서버 재기동 후 `init_db` 로그, 또는 `reseed_vfs.py` (개발 DB만)                       |
| 보고서 내용이 허위 같음      | writer가 `/memory/` 없이 쓴 경우 → researcher 먼저 실행했는지, Admin에서 research 파일 확인 |
| Admin과 에이전트 규칙 불일치 | 디스크 `AGENTS.md` vs VFS `/AGENTS.md` 내용 비교                                |
| Opik 안 보임          | `OPIK_API_KEY` 설정 여부, `/api/status`                                      |


테스트 실행 (백엔드):

```bash
cd server
uv run pytest
```

---

## 8. 학습 순서 제안 (초보자 3일)


| 일차  | 할 일                                                                                                              |
| --- | ---------------------------------------------------------------------------------------------------------------- |
| 1일차 | 이 가이드 + [README.md](./README.md) 읽기 → 로컬 설치 → Chat으로 조사·보고서 한 번 요청                                               |
| 2일차 | [AGENTS.md](./AGENTS.md) 정독 → Admin에서 `/memory/`, `/skills/` 탐색 → `AGENTS.md` 한 줄 수정 후 동작 차이 관찰                  |
| 3일차 | PoC 시나리오 1개 정의 → [6.5절](#65-4단계--서브에이전트도구-확장-serverappagentpy-toolspy) 회의·상담 예시 참고 → `SKILL.md`·SubAgent 목록 팀 리뷰 |


---

## 9. 요약

- 이 저장소는 **멀티 에이전트 + Postgres VFS + 웹 UI**가 갖춰진 **SI용 AI 에이전트 뼈대**입니다.  
- 설치는 **Postgres + `server/.env` + `uv` / `npm`** 가 핵심입니다.  
- 실프로젝트 적용은 **코드 배포보다 `AGENTS.md`·`/skills/`·역할 분리·보안·검증 프로세스**를 먼저 맞추는 것이 중요합니다.  
- SubAgent가 많아질 때는 **회의(예약/회의록)·상담(조회/등록)** 처럼 도메인·권한별로 쪼개고, VFS 경로로 handoff ([6.5.1~6.5.6](#651-설계-원칙--기능이-아니라-역할로-쪼개기)).  
- 상세 계약·API·DB는 [ARCHITECTURE.md](./ARCHITECTURE.md), 에이전트 행동 규칙은 [AGENTS.md](./AGENTS.md)가 단일 기준입니다.

문서·템플릿 개선 제안은 프로젝트 PM 또는 테크 리드에게 공유해 주세요.