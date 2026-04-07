# Novel Factory v2.0 — 업그레이드 계획서

> NFC (Novel Forge Claude) v1.7 → **Novel Factory (NF)** v2.0 전환 계획

---

## 1. 현황 분석

### 현재 구조 (NFC v1.7)
- **실행 환경**: Claude Code CLI 위에서만 동작
- **AI 의존**: CLAUDE.md를 통해 Claude의 행동을 제어하는 구조. AI가 컨텍스트 파일을 읽고 직접 파일을 생성/편집
- **상태 관리**: `nfc/state.py`가 Phase 전이를 관리하지만, AI 호출 자체는 Claude Code에 위임
- **문제점**: Claude Code 없이는 동작 불가, 다른 AI 모델 사용 불가, 모든 Phase에 동일 모델 강제 적용

### 핵심 변경 요구사항
1. 이름 변경: Novel Forge Claude → **Novel Factory**
2. AI 비종속화: 어떤 LLM이든 붙일 수 있는 구조
3. Phase별 독립 AI 할당: 각 단계마다 다른 모델/프로바이더 지정 가능

---

## 2. 아키텍처 설계 — "AI 에이전트 파이프라인" 방식

### 2.1 핵심 컨셉: Phase별 에이전트 슬롯

기존의 "Claude Code에게 CLAUDE.md로 지시"하는 방식을 버리고, **NF 자체가 오케스트레이터**가 되어 각 Phase마다 독립적인 AI 에이전트를 호출하는 구조로 전환한다.

```
┌─────────────────────────────────────────────────────────┐
│                    Novel Factory Core                     │
│              (Python 오케스트레이터 + 상태 머신)            │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Phase 1  │  │ Phase 2  │  │ Phase 3  │  │ Phase 4  │ │
│  │ 기획 Agent│→│ 전개 Agent│→│ 집필 Agent│→│ 퇴고 Agent│ │
│  │          │  │          │  │          │  │          │ │
│  │ GPT-4o   │  │ Claude   │  │ Gemini   │  │ Claude   │ │
│  │ (예시)   │  │ (예시)   │  │ (예시)   │  │ (예시)   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│        │              │             │             │       │
│        └──────────────┴─────────────┴─────────────┘      │
│                    공유 컨텍스트 레이어                     │
│              (8개 md 파일 + episodes/ + state)            │
└─────────────────────────────────────────────────────────┘
```

### 2.2 왜 이 방식인가

| 방식 | 장점 | 단점 | 판단 |
|------|------|------|------|
| **A. Phase별 에이전트 슬롯** | 역할별 최적 모델 선택, 비용 최적화, 명확한 책임 분리 | 구현 복잡도 ↑ | ✅ 채택 |
| B. 단일 에이전트 + 모델 교체 | 간단함 | Phase별 프롬프트 분리가 어중간 | ❌ |
| C. 멀티 에이전트 자율 협업 | 화려함 | 제어 불가, PD 중심 철학에 반함 | ❌ |

**Phase별 에이전트 슬롯**이 최적인 이유:
- **기획(Phase 1)**은 창의성이 중요 → 추론 강한 모델 (예: Claude Opus, o1)
- **전개(Phase 2)**는 기존 맥락 이해가 핵심 → 긴 컨텍스트 모델 (예: Gemini 1.5 Pro)
- **집필(Phase 3)**은 문체와 분량이 핵심 → 한국어 웹소설 특화 튜닝 or 대용량 출력 모델
- **퇴고(Phase 4)**는 교정/교열 특화 → 비용 효율적 모델 (예: GPT-4o-mini, Haiku)

사용자가 "Phase 3에는 Claude Sonnet, Phase 4에는 GPT-4o-mini"처럼 자유롭게 조합할 수 있다.

---

## 3. 모듈 설계

### 3.1 새로운 패키지 구조

```
novel_factory/                    # novel_forge_claude/ → novel_factory/
├── nf.py                         # 엔트리포인트 (nfc.py → nf.py)
├── nf/                           # 패키지
│   ├── models.py                 # 데이터 모델 (기존 유지 + 확장)
│   ├── state.py                  # 상태 머신 (기존 유지)
│   ├── fileops.py                # 파일 시스템 관리 (기존 유지)
│   ├── cli.py                    # CLI 라우팅 (기존 확장)
│   ├── display.py                # 출력 포매팅 (기존 유지)
│   ├── interactive.py            # 대화형 REPL (기존 확장)
│   │
│   ├── providers/                # ★ 신규: AI 프로바이더 추상화 레이어
│   │   ├── __init__.py
│   │   ├── base.py               # AIProvider 추상 클래스
│   │   ├── openai_provider.py    # OpenAI (GPT-4o, o1, etc.)
│   │   ├── anthropic_provider.py # Anthropic (Claude Opus/Sonnet/Haiku)
│   │   ├── google_provider.py    # Google (Gemini 1.5/2.0)
│   │   ├── openrouter_provider.py# OpenRouter (다중 모델 게이트웨이)
│   │   ├── ollama_provider.py    # Ollama (로컬 모델)
│   │   └── custom_provider.py    # 사용자 정의 (OpenAI-호환 API)
│   │
│   ├── agents/                   # ★ 신규: Phase별 에이전트 정의
│   │   ├── __init__.py
│   │   ├── base_agent.py         # 에이전트 기본 클래스
│   │   ├── planning_agent.py     # Phase 1: 기획 에이전트
│   │   ├── development_agent.py  # Phase 2: 전개 에이전트
│   │   ├── writing_agent.py      # Phase 3: 집필 에이전트
│   │   └── revision_agent.py     # Phase 4: 퇴고 에이전트
│   │
│   ├── prompts/                  # ★ 신규: 프롬프트 템플릿 관리
│   │   ├── phase1_planning.md
│   │   ├── phase2_development.md
│   │   ├── phase3_writing.md
│   │   ├── phase4_revision.md
│   │   └── shared_instructions.md
│   │
│   └── config.py                 # ★ 신규: 프로젝트별 AI 설정 관리
│
├── projects/                     # 기존 구조 유지
├── AI_GUIDE.md                   # CLAUDE.md → AI_GUIDE.md (범용화)
├── NF_plan.md                    # NFC_plan.md → NF_plan.md
└── README.md
```

### 3.2 AI 프로바이더 추상화 (`providers/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class AIResponse:
    content: str
    model: str
    usage: dict  # {"input_tokens": N, "output_tokens": N}
    raw: dict    # 원본 응답

class AIProvider(ABC):
    """모든 AI 프로바이더가 구현해야 하는 인터페이스"""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """텍스트 생성"""
        pass

    @abstractmethod
    def name(self) -> str:
        """프로바이더 이름 (예: 'openai/gpt-4o')"""
        pass

    def supports_long_context(self) -> bool:
        """128K+ 컨텍스트 지원 여부"""
        return False
```

### 3.3 Phase별 에이전트 (`agents/base_agent.py`)

```python
class PhaseAgent:
    """각 Phase의 AI 작업을 담당하는 에이전트"""

    def __init__(self, provider: AIProvider, prompt_template: str):
        self.provider = provider
        self.prompt_template = prompt_template

    def execute(self, context: dict, user_input: str) -> AIResponse:
        """컨텍스트 + 사용자 입력 → AI 호출 → 응답 반환"""
        system_prompt = self._build_system_prompt(context)
        return self.provider.generate(
            system_prompt=system_prompt,
            user_message=user_input,
        )

    def _build_system_prompt(self, context: dict) -> str:
        """컨텍스트 파일들을 읽어 시스템 프롬프트 구성"""
        # 8개 md 파일 + 이전 에피소드 요약 + Phase별 지침
        pass
```

### 3.4 프로젝트별 AI 설정 (`config.py` + `state.json` 확장)

```json
// projects/{소설제목}/ai_config.json
{
  "default_provider": {
    "type": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key_env": "ANTHROPIC_API_KEY"
  },
  "phase_overrides": {
    "phase1_planning": {
      "type": "openai",
      "model": "gpt-4o",
      "api_key_env": "OPENAI_API_KEY",
      "temperature": 0.9
    },
    "phase2_development": null,
    "phase3_writing": {
      "type": "anthropic",
      "model": "claude-opus-4-20250514",
      "temperature": 0.8,
      "max_tokens": 8192
    },
    "phase4_revision": {
      "type": "openai",
      "model": "gpt-4o-mini",
      "temperature": 0.3
    }
  },
  "cost_tracking": true
}
```

`null`이면 `default_provider`를 사용한다.

---

## 4. CLAUDE.md → AI_GUIDE.md 전환

### 변경 원칙
- Claude 전용 지시문 → 범용 AI 지침으로 전환
- 모델별 특화 지시는 `prompts/` 디렉토리의 템플릿에서 처리
- AI_GUIDE.md는 "어떤 AI든 이 프로젝트에서 일할 때 따라야 할 규칙"이 됨

### AI_GUIDE.md 주요 구조
```markdown
# Novel Factory — AI 가이드

## 역할 정의
당신은 웹소설 창작을 돕는 AI 어시스턴트입니다.
PD(기획자)의 결정에 따르며, 제안만 하고 독단적 결정을 하지 않습니다.

## 워크플로우 규칙
(기존 CLAUDE.md의 Phase별 규칙을 모델 비종속적으로 재작성)

## 출력 형식
(JSON/마크다운 등 구조화된 출력 포맷 명시)

## 금지 사항
(기존과 동일하되 Claude 특화 표현 제거)
```

---

## 5. 실행 방식 변경

### 5.1 기존 (v1.7) — Claude Code 의존
```bash
# Claude Code를 열고 "소설 써줘"라고 대화
# Claude가 CLAUDE.md를 읽고 nfc.py를 실행하며 파일을 직접 편집
```

### 5.2 신규 (v2.0) — 독립 실행
```bash
# 초기 설정
nf config provider openai --model gpt-4o --phase default
nf config provider anthropic --model claude-sonnet-4-20250514 --phase phase3

# 기존처럼 사용
nf init "제목"
nf status

# 대화형 REPL (NF가 직접 AI를 호출)
nf

# Phase별 AI 확인
nf config show
# Phase 1 (기획):    openai/gpt-4o
# Phase 2 (전개):    openai/gpt-4o  (default)
# Phase 3 (집필):    anthropic/claude-sonnet-4-20250514
# Phase 4 (퇴고):    openai/gpt-4o  (default)
```

### 5.3 호환 모드 — Claude Code에서도 동작
Claude Code 사용자를 위해 "패스스루 모드"를 제공한다. AI_GUIDE.md를 읽은 Claude Code가 기존처럼 nf.py 명령어를 실행하되, AI 호출은 Claude Code 자신이 수행한다.

```bash
nf config mode passthrough   # Claude Code 호환 모드
nf config mode standalone    # NF가 직접 API 호출 (기본값)
```

---

## 6. 구현 로드맵

### Phase A: 기반 작업 (1주)
- [ ] 레포 이름 및 패키지명 변경 (nfc → nf)
- [ ] `providers/base.py` 추상 클래스 작성
- [ ] `providers/anthropic_provider.py` 구현 (기존 Claude 사용자 지원)
- [ ] `providers/openai_provider.py` 구현
- [ ] `config.py` — 프로젝트별 AI 설정 로드/저장
- [ ] 기존 CLI 명령어 호환성 유지

### Phase B: 에이전트 레이어 (1주)
- [ ] `agents/base_agent.py` — 컨텍스트 주입 + AI 호출 + 응답 파싱
- [ ] `prompts/` — CLAUDE.md에서 Phase별 프롬프트 분리/범용화
- [ ] Phase 1~4 각각의 에이전트 구현
- [ ] 상태 머신(`state.py`)과 에이전트 연결

### Phase C: 추가 프로바이더 + UX (1주)
- [ ] `providers/google_provider.py` (Gemini)
- [ ] `providers/openrouter_provider.py` (다중 모델)
- [ ] `providers/ollama_provider.py` (로컬 모델)
- [ ] `nf config` CLI 확장 (provider/phase 매핑)
- [ ] 비용 추적 기능 (토큰 사용량 집계)

### Phase D: 고급 기능 (1주)
- [ ] A/B 테스트 모드: 같은 Phase에 2개 모델을 붙여 결과 비교
- [ ] 프롬프트 버저닝: prompts/ 하위 v1, v2 관리
- [ ] Passthrough 모드 (Claude Code 호환)
- [ ] README, AI_GUIDE.md 완성
- [ ] 통합 테스트

---

## 7. 마이그레이션 가이드 (v1.7 → v2.0)

### 기존 사용자를 위한 전환 절차

```bash
# 1. 패키지 이름 변경
mv novel_forge_claude novel_factory

# 2. 의존성 설치
pip install openai anthropic google-generativeai

# 3. API 키 설정
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

# 4. 기존 프로젝트 마이그레이션 (자동)
nf migrate projects/my-novel
# → state.json에 ai_config 필드 추가
# → CLAUDE.md → AI_GUIDE.md 복사

# 5. 동일하게 사용
nf status
nf  # REPL 진입
```

### 하위 호환성
- 기존 CLI 명령어 100% 유지 (`nfc.py` → `nf.py` 심볼릭 링크 제공)
- 프로젝트 디렉토리 구조 변경 없음
- `state.json` 스키마 하위 호환 유지 (ai_config 필드만 추가)
- Claude Code passthrough 모드로 기존 워크플로우 그대로 사용 가능

---

## 8. 추가 아이디어 — 에이전트 모드 확장

### 8.1 "AI 편집회의" 모드
Phase 2(전개 선정)에서 여러 AI를 동시에 호출하여 각각 다른 관점의 전개 옵션을 제안받는 모드:

```
PD: "다음 전개를 제안해줘" (AI 편집회의 모드 ON)

  AI-A (GPT-4o):      일반 전개 2개 제안
  AI-B (Claude Opus):  의외의 전개 2개 제안
  AI-C (Gemini):       중간 전개 1개 제안

→ 5개 옵션이 PD에게 제시됨
```

### 8.2 "크로스 체크" 모드
Phase 4(퇴고)에서 서로 다른 AI가 교차 검증:

```
AI-A가 1차 퇴고 → AI-B가 2차 검수 → 불일치 부분만 PD에게 보고
```

### 8.3 비용 최적화 자동 모드
Phase별 특성에 맞게 자동으로 모델 추천:

```bash
nf config auto-optimize
# Phase 1 → 추론 강함, 고비용 허용 → claude-opus-4-20250514
# Phase 2 → 긴 컨텍스트 필요 → gemini-2.0-pro
# Phase 3 → 대량 출력, 문체 → claude-sonnet-4-20250514
# Phase 4 → 교정/교열 특화, 저비용 → gpt-4o-mini
```

---

## 9. v2.1 패치: 언제든 퇴고 모드

v2.1에서는 퇴고 워크플로우를 개선하여 **어느 단계에서든 이전 회차를 퇴고**할 수 있도록 변경했다.

### 9.1 기존 제한 (v1.7~v2.0)

```
revise-episode는 다음 단계에서만 사용 가능:
- development_proposal (Phase 2)
- complete (Phase 4)
```

### 9.2 변경 사항 (v2.1)

```
revise-episode를 대부분의 단계에서 사용 가능:
- 제외: direction_decision, plan_buildup, writing, proofreading
- 조건: episode_count > 0, revision_mode가 아닐 때
```

### 9.3 새로운 퇴고 흐름

```
PD: "3화 퇴고하자"
    ↓
nf revise-episode ep003.md
    ↓
drafts/revision_ep003.md 생성 (원본 복사)
    ↓
Phase 4 proofread_decision으로 직접 진입
    ↓
AI가 퇴고본 작성
    ↓
PD 검토: [A]pprove / [M]odify / [D]ismiss
    ↓
승인 → context_update → next
    ↓
episodes/ep003.md 덮어쓰기 + 원래 단계로 복귀
```

### 9.4 구현 변경점

| 파일 | 변경 내용 |
|------|----------|
| `nf/state.py` | `validate_action`에서 revise-episode 특별 처리 |
| `nf/state.py` | `execute_action`에서 동적 전이 (proofread_decision 직행) |
| `nf/state.py` | revision_mode에서 reject 시 원래 단계 복귀 |
| `nf/state.py` | revision_mode에서 context_update 후 바로 복귀 |

---

## 10. 요약

| 항목 | v1.7 (NFC) | v2.0 (NF) | v2.1 |
|------|-----------|-----------|------|
| 이름 | Novel Forge Claude | **Novel Factory** | - |
| AI 의존 | Claude Code 전용 | 아무 LLM | - |
| AI 호출 | Claude Code가 직접 수행 | NF 오케스트레이터가 API 호출 | - |
| Phase별 AI | 불가 | Phase별 독립 모델 지정 가능 | - |
| 프롬프트 | CLAUDE.md 단일 파일 | Phase별 분리된 프롬프트 템플릿 | - |
| 실행 방식 | Claude Code 필수 | 독립 실행 + Claude Code 호환 | - |
| 컨텍스트 시스템 | 8개 md 파일 | 동일 | - |
| PD 의사결정 | 동일 | 동일 | - |
| **퇴고 진입** | 특정 단계만 | 특정 단계만 | **언제든 가능** |
