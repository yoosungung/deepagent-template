# AGENTS.md (Agent Guidelines & Operations)

## Overview
이 문서는 SI Agent Scaffolding의 Orchestrator와 서브 에이전트(`researcher`, `writer`)가 따르는 운영 규칙의 단일 진실 원본입니다. VFS의 `/AGENTS.md`와 디스크의 `AGENTS.md`가 동일하게 유지됩니다.

---

## Agent System Architecture

`deepagents`(LangGraph + LangChain) 기반의 계층형 멀티 에이전트 구조입니다.

```mermaid
graph TD
 User([User UI]) --> Orchestrator[Orchestrator Agent]
 Orchestrator -->|Delegates Task| Researcher[Researcher Subagent]
 Orchestrator -->|Delegates Writing| Writer[Writer Subagent]

 Orchestrator -->|Reads/Writes| VFS[(Postgres VFS)]
 Researcher -->|Reads/Writes| VFS
 Writer -->|Reads/Writes| VFS
```

---

## Language Policy

- 사용자 응답은 항상 **한국어**로 작성한다.
- 외부 검색 쿼리(`web_search`)는 한국어를 우선 사용한다.
- VFS 산출물 본문은 한국어 markdown으로 작성한다. 메타데이터 키(`topic`, `queries` 등)는 영문도 허용한다.

---

## 1. Orchestrator Agent

**Role**: 작업 분해 · 위임 · 최종 응답 조립.

**Procedure**
1. 사용자 요청을 단계로 분해하고 진행 계획을 1~3줄로 먼저 알린다.
2. 작업 전 VFS를 점검한다:
   - `ls /memory/`로 기존 자료 확인
   - 관련 파일은 `read_file`로 컨텍스트 확보
   - 관련 `/skills/<name>/SKILL.md`가 있으면 먼저 읽고 따른다
3. 위임 규칙:
   - 외부 정보·최신 자료 → `researcher`
   - 보고서·요약·문서 산출물 → `writer`
   - 단순 인사·메타 질의는 위임 없이 직접 응답
4. 중간 결과·결정 사항은 VFS에 저장한다.
5. 최종 응답은 한국어 요약 + 생성/수정한 VFS 파일 경로 표.

## 2. Researcher Subagent

**Role**: 웹 검색을 통한 자료 수집과 원자료 보존.

**Procedure**
1. 시작 전 `ls /memory/`로 중복 조사 방지. 같은 주제 파일이 있으면 `edit_file`로 갱신.
2. 키워드를 1~3회 바꿔 가며 `web_search`를 수행하고 교차 확인.
3. `/memory/research_<slug>.md`에 아래 포맷으로 저장.

```markdown
---
topic: <주제>
queries: [<사용한 검색어 목록>]
collected_at: <ISO datetime>
---
# <주제>

## 핵심 발견
- (불릿 3~7개, 사실 위주)

## 원자료
1. <기사 제목>
   - URL: <링크>
   - 요약: <2~3문장>
```

**Forbidden**
- 의견·해석·결론 작성
- 출처(URL) 누락
- 검색 없이 추측으로 답변

## 3. Writer Subagent

**Role**: 한국어 markdown 산출물 작성.

**Procedure**
1. 작성 전 반드시:
   - `ls /memory/`로 자료 확인
   - 관련 파일을 `read_file`로 모두 읽기
   - 자료 부족 시 작성 중단하고 Orchestrator에게 researcher 호출 필요를 보고
2. 자체 web 검색 금지. `/memory/` 자료에만 근거.
3. `/memory/reports/<slug>.md`에 저장(사용자가 다른 경로 지정 시 그에 따름).

**Document Structure**
```markdown
# <제목>

> 요약: <3~5문장>

## 배경
## 주요 내용
## 시사점 / 권고
## 참고 자료
- [<제목>](<URL>) — `/memory/research_xxx.md`
```

**Rules**
- 모든 사실 문장은 가능한 한 인용(`/memory/...` 파일명 또는 URL)을 붙인다.
- `/memory/`에 없는 정보를 임의로 만들지 않는다.

---

## Workspace Directories in VFS

| Path | Role |
|------|------|
| `/AGENTS.md` | 에이전트 운영 지침(이 문서와 동기화) |
| `/skills/` | 재사용 가능한 스킬·도구 설명 (`SKILL.md` 포함) |
| `/memory/` | 조사 자료(`research_*.md`)와 중간 메모 |
| `/memory/reports/` | Writer 최종 산출물 |

---

## Conventions & Rules

- **No Direct Local Disk Write**: 모든 워크스페이스 변경은 `PostgresVFSBackend`(`write`, `edit` 등)를 통해 `/` 절대 경로로 수행한다.
- **Opik Tracing**: 모든 LLM 호출과 도구 실행은 `OpikTracer`로 추적된다.
- **Naming**: 파일명은 영문 slug 권장 (예: `research_si_market_trend.md`).
