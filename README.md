# Novel Factory (NF) v2.0

PD(기획자)와 AI가 협업하여 웹소설을 기획하고 집필하는 인터랙티브 작성 도구.

**v2.0 핵심 변경**: AI 비종속화 — Phase별로 다른 LLM(OpenAI, Anthropic, Google, Ollama 등)을 자유롭게 조합할 수 있다.

> 이전 버전(Novel Forge Claude v1.7)은 [`legacy/nfc-v1.7`](../../tree/legacy/nfc-v1.7) 브랜치에서 확인할 수 있다.

## 시작하기

### 요구사항

- Python 3.10+
- AI 프로바이더 패키지 (사용할 것만 설치):
  ```bash
  pip install anthropic          # Anthropic (Claude)
  pip install openai             # OpenAI (GPT-4o, o1 등)
  pip install google-generativeai # Google (Gemini)
  # Ollama, OpenRouter는 추가 패키지 불요
  ```

### 실행

```bash
# 독립 실행 (standalone 모드)
python nf.py                     # 대화형 REPL 진입
python nf.py init "제목"          # 새 프로젝트 생성
python nf.py status              # 현재 상태 확인

# Claude Code에서 실행 (passthrough 모드)
# 프로젝트 폴더에서 Claude Code를 열고 "소설 써줘"라고 입력

# 하위 호환 (v1.7 명령어 그대로 동작)
python nfc.py status
```

### AI 프로바이더 설정

```bash
# 기본 프로바이더 설정
python nf.py ai-provider anthropic -m claude-sonnet-4-20250514

# Phase별 다른 모델 지정
python nf.py ai-provider openai -m gpt-4o --phase phase1
python nf.py ai-provider anthropic -m claude-opus-4-20250514 --phase phase3
python nf.py ai-provider openai -m gpt-4o-mini --phase phase4

# 로컬 모델 (Ollama)
python nf.py ai-provider ollama -m llama3.1 --phase phase2

# 설정 확인 / 검증
python nf.py ai-config
python nf.py ai-validate
```

### 멀티 프로젝트

```bash
# CWD 기반 자동 감지
cd projects/my-novel
python ../../nf.py status

# --project 옵션으로 명시적 지정
python nf.py status --project my-novel
python nf.py -P my-novel status
```

## 워크플로우

```
Phase 1: 컨텍스트 수립 (최초 1회)
  경로 A) 장르/키워드 입력 → 방향성 5개 제안 → PD 선정 → 기획안 → 컨텍스트 확정
  경로 B) 기존 원고 임포트 → AI 분석 → 컨텍스트 생성 → PD 검토
  경로 C) 기존 컨텍스트 임포트 → Phase 2 직행

  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  Phase 2: 전개 선정                                  │
  │    전개 옵션 5개 생성 (일반2/중간1/희귀2) → PD 1개 선정│
  │                    ↓                                │
  │  Phase 3: 집필                                       │
  │    문체 설정 → 작성 모드 선택 (auto/scene/episode,    │
  │    상호 배타) → 원고 작성 → PD 승인                    │
  │                    ↓                                │
  │  Phase 4: 퇴고 및 컨텍스트 갱신                       │
  │    퇴고 → PD 승인 → 컨텍스트 업데이트 → Phase 2로 복귀 │
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

## 의사결정 단축키

### 항목 선택 (방향성/전개 선정)

| 단축키 | 명령 | 설명 |
|--------|------|------|
| `S <id>` | select | **[S]elect** — 항목 선정 (1개) |
| `H <id>` | hold | **[H]old** — 항목 보류 |
| `D <id>` | discard | **[D]iscard** — 항목 폐기 |
| `R` | retry | **[R]etry** — 전체 재생성 |
| `C` | confirm-end | **[C]onfirm** — 선정 종료 (Phase 2) |

### 결과물 검토 (기획안/원고/퇴고)

| 단축키 | 명령 | 설명 |
|--------|------|------|
| `A` | approve | **[A]pprove** — 승인 |
| `M "피드백"` | revise | **[M]odify** — 수정 요청 |
| `D` | reject | **[D]ismiss** — 폐기 |
| `H` | hold | **[H]old** — 보류 (Phase 3 집필 중) |

한국어 자연어 입력도 지원한다. ("2번", "승인", "다시 해줘" 등)

## CLI 명령어

```
python nf.py <command>
```

### 기본 명령

| 명령어 | 단축키 | 설명 |
|--------|--------|------|
| `init <name> [--title <dir>]` | — | 새 프로젝트 생성 |
| `status` | — | 현재 상태 표시 |
| `items` | — | 제안 항목 목록 |
| `add "<text>" [-p 0.XX]` | — | 항목 추가 |
| `select <id>` | `S` | 항목 선정 (1개만) |
| `hold <id>` | `H` | 항목 보류 |
| `discard <id>` | `D` | 항목 폐기 |
| `retry` | `R` | 전체 재생성 |
| `approve` | `A` | 승인 |
| `revise "<feedback>"` | `M` | 수정 요청 |
| `reject` | `D` | 결과물 폐기 |
| `confirm-end` | `C` | 전개 선정 종료 (Phase 2) |
| `save <type> <file>` | — | 초안 저장 (plan/manuscript/proofread) |
| `config <key> <value>` | — | 설정 변경 (style_reference, writing_mode, auto_write) |
| `context-update` | — | 컨텍스트 갱신 완료 |
| `context-backup` | — | 컨텍스트 백업 |
| `next` | — | 다음 단계 진행 |
| `import-manuscript <file>` | — | 기존 원고 임포트 |
| `import-context` | — | 기존 컨텍스트 파일 임포트 |
| `pd-proofread <file>` | — | PD 자체 퇴고 원고 등록 |
| `switch-auto` | — | 자동작성 모드로 전환 |
| `merge-episode` | — | 장면들을 에피소드로 병합 (scene 모드, 5,500자+) |
| `scenes` | — | 장면 목록 및 글자 수 표시 |
| `revise-episode <file>` | — | 완성된 에피소드 재수정 |

### v2.0 AI 설정 명령

| 명령어 | 설명 |
|--------|------|
| `ai-config` | AI 프로바이더 설정 표시 |
| `ai-provider <type> -m <model> [--phase <phase>]` | Phase별 프로바이더 설정 |
| `ai-validate` | 프로바이더 설정 검증 (API 키 등) |
| `ai-mode` | standalone/passthrough 모드 확인 |
| `ai-cost` | 토큰 사용량 요약 |
| `ai-cost-reset` | 비용 추적 로그 초기화 |

### v2.2 앙상블 명령

| 명령어 | 설명 |
|--------|------|
| `ensemble-dev [--workers <list>]` | Phase 2 전개안을 여러 CLI worker로 병렬 생성 (기본 `gemini-cli,codex-cli`) → `drafts/ensemble_dev_*.md` |

여러 AI를 동원해 전개안 다양성을 확보하는 **하이브리드 앙상블**. NF가 외부 CLI(gemini, codex 등)를 병렬 실행해 후보를 모으면, Claude Code가 자체 배치를 더해 source별로 PD에게 전체 제시하고, PD가 최종 선택한다.

### v2.3 집필 파이프라인

| 명령어 | 설명 |
|--------|------|
| `draft-pipeline [--draft <t>] [--revise <t>]` | 역할 분담형 릴레이 집필 (Gemini 초고 → Codex 1차 퇴고 자동) |

강점이 다른 3개 모델이 한 회차를 **릴레이**로 완성하는 파이프라인:

| 단계 | 담당 | 역할 | 산출물 |
|------|------|------|--------|
| 초고 | **Gemini** | 전개+컨텍스트 기반 막 갈김 (분량·기세 우선) | `01_draft_gemini.md` |
| 1차 퇴고 | **Codex** | 맞춤법·오탈자·비문·설정 표기 오류 (라인 레벨) | `02_revise1_codex.md` |
| 2차 퇴고 | **Claude Code** | 컨텍스트 정합성 검수 + PD 최종 승인 | `03_revise2_claude.md` |

1·2단계는 `draft-pipeline`으로 자동 실행되고, 3단계와 승인은 라이브 Claude Code가 수행한다. 모든 단계가 `episodes/ep###_making/`에 **새 파일로 보존**되어 제작 히스토리가 남는다 (덮어쓰기 없음). 승인된 최종본만 `episodes/ep###.md`로 승격된다.

### 지원 프로바이더

| 타입 | 모델 예시 | API 키 환경변수 |
|------|----------|----------------|
| `anthropic` | claude-opus-4-20250514, claude-sonnet-4-20250514 | `ANTHROPIC_API_KEY` |
| `openai` | gpt-4o, gpt-4o-mini, o1, o3 | `OPENAI_API_KEY` |
| `google` | gemini-2.0-flash, gemini-2.5-pro | `GOOGLE_API_KEY` |
| `openrouter` | anthropic/claude-sonnet-4, etc. | `OPENROUTER_API_KEY` |
| `ollama` | llama3.1, mistral, etc. | (불필요) |
| `custom` | 임의 모델 (OpenAI 호환 API) | 사용자 지정 |
| `gemini-cli` | (CLI 기본 모델 또는 `-m`) | (CLI 로그인) |
| `codex-cli` | (CLI 기본 모델 또는 `-c model=`) | (CLI 로그인) |
| `claude-cli` | (CLI 기본 모델 또는 `--model`) | (CLI 로그인) |

> **v2.2 CLI 프로바이더**: HTTP API 대신 로컬에 설치된 에이전트 CLI(`gemini`, `codex`, `claude`)를 subprocess로 호출한다. API 키 대신 각 CLI의 로그인 세션을 사용한다. Phase 2 앙상블(`ensemble-dev`)의 worker로 활용된다.

## 프로젝트 구조

```
novel_factory/
├── nf.py                    # 엔트리포인트
├── nfc.py                   # 하위 호환 래퍼
├── nf/                      # 코어 패키지
│   ├── models.py            # 데이터 모델 (Phase, Step, Item, ProjectState)
│   ├── state.py             # 상태 머신 (전이, 검증, 실행)
│   ├── fileops.py           # 파일 시스템 관리
│   ├── cli.py               # CLI 라우팅
│   ├── display.py           # 출력 포매팅
│   ├── interactive.py       # 대화형 REPL
│   ├── config.py            # v2.0: 프로젝트별 AI 설정 (ai_config.json)
│   ├── orchestrator.py      # v2.0: Phase↔에이전트 연결
│   ├── cost_tracker.py      # v2.0: 토큰 사용량 추적
│   ├── providers/           # v2.0: AI 프로바이더 추상화
│   │   ├── base.py          # AIProvider 추상 클래스
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   ├── google_provider.py
│   │   ├── openrouter_provider.py
│   │   └── ollama_provider.py
│   ├── agents/              # v2.0: Phase별 에이전트
│   │   ├── base_agent.py    # 컨텍스트 주입 + AI 호출
│   │   ├── planning_agent.py    # Phase 1: 기획
│   │   ├── development_agent.py # Phase 2: 전개
│   │   ├── writing_agent.py     # Phase 3: 집필
│   │   └── revision_agent.py    # Phase 4: 퇴고
│   └── prompts/             # v2.0: Phase별 프롬프트 템플릿
│       ├── phase1_planning.md
│       ├── phase2_development.md
│       ├── phase3_writing.md
│       ├── phase4_revision.md
│       └── shared_instructions.md
├── projects/                # 소설 프로젝트 저장소
│   └── {소설제목}/
│       ├── state.json
│       ├── ai_config.json   # v2.0: Phase별 AI 설정
│       ├── cost_log.json    # v2.0: 토큰 사용량 로그
│       ├── context/         # 컨텍스트 (6개 필수 + foreshadow/payoff)
│       ├── episodes/        # 완성 원고
│       ├── drafts/          # 작업 중 초안
│       ├── shelve/          # 보류 항목
│       ├── polishing/guideline.md
│       └── backup/
├── ideas/                   # 소설 아이디어/컨셉 보관함 (git 미추적, 로컬 전용)
├── AI_GUIDE.md              # v2.0: 범용 AI 가이드 (모델 무관)
├── CLAUDE.md                # Claude Code 전용 행동 매뉴얼
└── NF_v2.0_plan.md          # 업그레이드 계획서
```

## 핵심 개념

### PD 중심 의사결정

AI는 제안만 하고, 모든 결정은 PD(사용자)가 내린다.

### Phase별 AI 에이전트 (v2.0)

각 Phase에 최적화된 AI 모델을 독립 배치할 수 있다:

| Phase | 역할 | 추천 모델 특성 |
|-------|------|---------------|
| Phase 1 (기획) | 방향성, 기획안, 컨텍스트 | 창의성 + 추론 |
| Phase 2 (전개) | 전개 옵션 생성 | 긴 컨텍스트 이해 |
| Phase 3 (집필) | 에피소드 집필 | 문체 + 대용량 출력 |
| Phase 4 (퇴고) | 교정/교열 | 비용 효율 + 정확성 |

### 컨텍스트 시스템

8개 마크다운 파일이 소설의 현재 상태를 추적한다:

| 파일 | 내용 |
|------|------|
| `character_profiles.md` | 캐릭터 프로필 및 관계도 |
| `setting_world.md` | 세계관, 배경 설정 |
| `concept.md` | 로그라인, 장르, 매력 포인트 |
| `plot_outline.md` | 플롯 뼈대, 진행 상황 |
| `themes.md` | 테마, 상징물 |
| `tone.md` | 톤앤매너, 분량 설정 |
| `foreshadow.md` | 미회수 복선 목록 |
| `payoff.md` | 회수된 복선 기록 |

### 전개 옵션 확률 분포

| 구분 | 개수 | probability 범위 | 설명 |
|------|------|------------------|------|
| **일반(Normal)** | 2개 | > 0.30 | 자연스럽고 예측 가능한 전개 |
| **중간(Moderate)** | 1개 | 0.10 ~ 0.30 | 약간 의외이지만 납득 가능한 전개 |
| **희귀(Rare)** | 2개 | < 0.10 | 매우 독창적이고 기발한 전개 |

### 작성 모드 (상호 배타)

| 모드 | 설명 | 분량 |
|------|------|------|
| **auto** | AI가 3화를 자율 연쓰기 | 3화 × 5,500자+ |
| **scene** | 장면별 작성 → `merge-episode`로 병합 | 병합 시 5,500자+ |
| **episode** | 1화 분량 일괄 작성 | 5,500자+ |

### standalone vs passthrough 모드 (v2.0)

| 모드 | 설명 |
|------|------|
| **standalone** | NF가 직접 AI API를 호출 (기본값) |
| **passthrough** | Claude Code 등 외부 AI가 콘텐츠 생성 (기존 v1.7 방식) |
