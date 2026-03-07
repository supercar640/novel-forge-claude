# Novel Forge Claude (NFC) v1.7

PD(기획자)와 AI가 협업하여 웹소설을 기획하고 집필하는 인터랙티브 작성 도구.

Claude Code 위에서 동작하며, PD가 의사결정을 내리고 AI가 콘텐츠를 생성하는 4단계 순환 워크플로우로 소설을 완성한다.

## 시작하기

### 요구사항

- Python 3.10+
- [Claude Code](https://claude.ai/code) CLI

### 실행

```bash
# Claude Code에서 실행 (권장)
# novel_forge_claude 폴더에서 Claude Code를 열고 "소설 써줘"라고 입력

# CLI 직접 실행
python nfc.py status          # 현재 상태 확인
python nfc.py init "제목"     # 새 프로젝트 생성

# 대화형 모드
python nfc.py                 # 인자 없이 실행하면 REPL 진입
```

## 워크플로우

```
Phase 1: 컨텍스트 수립 (최초 1회)
  경로 A) 장르/키워드 입력 → 방향성 5개 제안 → PD 선정 → 기획안 작성 → PD 승인 → 컨텍스트 확정
  경로 B) 기존 원고 임포트 → AI 분석 → 컨텍스트 생성 → PD 검토 → Phase 2 (v1.5)
  경로 C) 기존 컨텍스트 임포트 → Phase 2 직행 (v1.5)

  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  Phase 2: 전개 선정                                  │
  │    전개 옵션 5개 생성 (일반2/중간1/희귀2) → PD 1개 선정│
  │                    ↓                                │
  │  Phase 3: 집필                                       │
  │    문체 설정 → 작성 모드 선택 (auto/scene/episode,    │
  │    상호 배타) → 원고 작성 → PD 승인                    │
  │    (scene 모드: 장면별 검토 → merge-episode → 승인)   │
  │                    ↓                                │
  │  Phase 4: 퇴고 및 컨텍스트 갱신                       │
  │    퇴고 → PD 승인 → 컨텍스트 업데이트 → Phase 2로 복귀 │
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

Phase 2 → 3 → 4 → 2 사이클이 연재 종료까지 반복된다.

## 의사결정 단축키

모든 단계에서 영어 한 글자로 빠르게 응답할 수 있다.

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
| `H` | hold | **[H]old** — 보류 (Phase 3 집필 중, v1.7) |

한국어 자연어 입력도 지원한다. ("2번", "승인", "다시 해줘" 등)

## CLI 명령어

```
python nfc.py <command>
```

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
| `import-manuscript <file>` | — | 기존 원고 임포트 (v1.5) |
| `import-context` | — | 기존 컨텍스트 파일 임포트 (v1.5) |
| `pd-proofread <file>` | — | PD 자체 퇴고 원고 등록 (v1.5) |
| `switch-auto` | — | 자동작성 모드로 전환 (v1.5) |
| `merge-episode` | — | 장면들을 에피소드로 병합 (scene 모드, 5,500자 이상) |
| `scenes` | — | 장면 목록 및 글자 수 표시 (scene 모드) |
| `revise-episode <file>` | — | 완성된 에피소드를 재수정 모드로 진입 (v1.7) |

## 프로젝트 구조

```
novel_forge_claude/
├── nfc.py                  # 엔트리포인트
├── nfc/                    # CLI 패키지
│   ├── models.py           # 데이터 모델 (Phase, Step, Item, ProjectState)
│   ├── state.py            # 상태 머신 (전이, 검증, 실행)
│   ├── fileops.py          # 파일 시스템 관리 (인코딩 검증 포함)
│   ├── cli.py              # CLI 라우팅
│   ├── display.py          # 출력 포매팅
│   └── interactive.py      # 대화형 REPL
├── projects/               # 소설 프로젝트 저장소
│   └── {소설제목}/
│       ├── state.json      # 워크플로우 상태
│       ├── context/        # 활성 컨텍스트 (8개 md 파일)
│       │   ├── character_profiles.md
│       │   ├── setting_world.md
│       │   ├── concept.md
│       │   ├── plot_outline.md
│       │   ├── themes.md
│       │   ├── tone.md
│       │   ├── foreshadow.md   # 미회수 복선 (v1.5)
│       │   └── payoff.md       # 회수된 복선 (v1.5)
│       ├── episodes/       # 완성 원고 (PD: ep001.md, auto: auto_ep001.md)
│       ├── drafts/         # 작업 중 초안
│       ├── shelve/         # 보류된 아이디어/전개/초안 (v1.7)
│       ├── polishing/      # 퇴고 관련 (v1.5)
│       │   └── guideline.md
│       └── backup/         # 컨텍스트 백업
├── CLAUDE.md               # Claude Code 행동 매뉴얼
├── NFC_plan.md             # 전체 기획 스펙
└── README.md
```

## 핵심 개념

### PD 중심 의사결정

AI는 제안만 하고, 모든 결정은 PD(사용자)가 내린다. 선정/보류/폐기/수정/리트라이가 모든 단계에서 일관되게 적용된다.

### 컨텍스트 시스템

8개 마크다운 파일이 소설의 현재 상태를 추적한다:

| 파일 | 내용 |
|------|------|
| `character_profiles.md` | 캐릭터 프로필 및 관계도 |
| `setting_world.md` | 세계관, 배경 설정 |
| `concept.md` | 로그라인, 장르, 매력 포인트 |
| `plot_outline.md` | 플롯 뼈대, 진행 상황 |
| `themes.md` | 테마, 상징물, 복선 추적 |
| `tone.md` | 톤앤매너, 분량 설정 |
| `foreshadow.md` | 미회수 복선 목록 (v1.5) |
| `payoff.md` | 회수된 복선 기록 (v1.5) |

매 회차 완료 시 자동으로 갱신되며, 크기가 커지면 백업 후 요약 압축한다.

### 전개 옵션 확률 분포 (v1.5 3-카테고리)

Phase 2에서 생성하는 5개 전개 옵션은 3-카테고리 확률 분포 규칙을 따른다:

| 구분 | 개수 | probability 범위 | 설명 |
|------|------|------------------|------|
| **일반(Normal)** | 2개 | > 0.30 | 자연스럽고 예측 가능한 전개 |
| **중간(Moderate)** | 1개 | 0.10 ~ 0.30 | 약간 의외이지만 납득 가능한 전개 |
| **희귀(Rare)** | 2개 | < 0.10 | 매우 독창적이고 기발한 전개 |

이를 통해 뻔한 전개와 의외의 전개를 균형 있게 제시한다.

### 복선 관리 (v1.5)

- `foreshadow.md`: 설치된 복선 중 아직 회수되지 않은 것들을 추적
- `payoff.md`: 회수 완료된 복선과 회수 시점을 기록
- 매 회차 컨텍스트 갱신 시 자동 업데이트

### 퇴고 가이드라인 (v1.5)

`polishing/guideline.md`에 작품별 퇴고 기준을 정의하여 AI 퇴고 시 일관된 품질을 유지한다.

### 유연한 시작 경로 (v1.5)

- **기본**: 장르/키워드 입력 → 방향성 선정 → 기획안 → 컨텍스트 생성
- **원고 임포트**: 기존 원고 파일 → AI 분석 → 컨텍스트 자동 생성
- **컨텍스트 임포트**: 기존 context/ 파일 활용 → Phase 2 직행

### 보류 항목 보관 — shelve/ (v1.7)

보류(Hold)된 항목은 `shelve/` 디렉토리에 자동 저장되어 나중에 참조할 수 있다:

| 파일 접두어 | 출처 | 설명 |
|------------|------|------|
| `idea_*.md` | Phase 1 방향성 | 보류된 방향성 아이디어 |
| `dev_*.md` | Phase 2 전개 | 보류된 전개 옵션 |
| `draft_*.md` | Phase 3 원고 | 보류된 초안 |

### 작성 모드 상호 배타 (v1.7)

auto와 scene/episode는 상호 배타적으로 선택한다. 하나를 설정하면 다른 쪽이 자동 해제된다.

| 모드 | 설명 | 분량 |
|------|------|------|
| **auto** (자동작성) | AI가 3화를 자율 연쓰기 | 3화 × 5,500자 이상 |
| **scene** (장면별) | PD 확인하며 장면별 작성 → `merge-episode`로 수동 병합 | 장면 단위 (병합 시 5,500자 이상) |
| **episode** (1화 분량) | PD 확인하며 1화 분량 일괄 작성 | 5,500자 이상 |

### 과거 회차 재수정 (v1.7)

이미 완성된 에피소드를 `revise-episode <file>` 명령으로 수정할 수 있다.

- Phase 2 시작(`development_proposal`) 또는 회차 완료(`complete`) 단계에서 진입 가능
- 에피소드가 `drafts/`에 복사되어 `writing_decision` 단계로 진입
- 수정 → 퇴고 → 컨텍스트 갱신 후 원본 에피소드를 덮어쓰기
- `episode_count`는 변하지 않음 (재수정이므로)
- 완료 후 원래 단계로 자동 복귀
