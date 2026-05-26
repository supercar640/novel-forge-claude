# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Novel Factory (NF) v2.0** — PD(기획자)와 AI가 협업하여 웹소설을 기획하고 집필하는 인터랙티브 작성 도구. 전체 스펙은 `NF_v2.0_plan.md`에 정의되어 있다. 범용 AI 가이드는 `AI_GUIDE.md` 참조.

**핵심 원칙**: CLI(`python nf.py <cmd>`)는 상태 관리 도구이고, 콘텐츠 생성은 standalone 모드에서 NF가 직접 AI API를 호출하거나, passthrough 모드에서 Claude Code가 수행한다.

> **v2.0 변경사항**: nfc→nf 리네임, Phase별 AI 프로바이더 지정 가능, `python nf.py`도 하위 호환으로 동작.

---

## 토큰 효율화 규칙

1. **context/ 재읽기 금지**: 같은 세션 내에서 이미 읽은 context/ 파일은 재읽기하지 않는다. 내용을 기억하고 있다면 Read 도구를 다시 호출하지 말 것.
2. **status 최소 호출**: CLI `status`는 상태 확인이 반드시 필요할 때만 호출한다. 직전에 실행한 명령의 출력으로 상태를 파악할 수 있으면 status를 생략한다.
3. **items 불필요 호출 금지**: add 직후 items를 호출하지 않는다. add의 출력으로 충분하다.
4. **Phase 4 컨텍스트 갱신 시**: 퇴고 단계에서 이미 읽은 원고와 컨텍스트를 다시 읽지 않는다. 같은 세션이면 기억된 내용으로 갱신한다.

---

## 단축키 (Shortcut)

사용자는 영어 약자 한 글자로 의사결정을 입력할 수 있다. Claude Code는 이를 인식하여 적절한 CLI 명령으로 변환한다.

### 항목 선택 단계 (방향성/전개 선정)

| 단축키 | 명령 | 설명 |
|--------|------|------|
| `S <id>` | select | 항목 선정 (1개) |
| `H <id>` | hold | 항목 보류 |
| `D <id>` | discard | 항목 폐기 |
| `R` | retry | 전체 재생성 |
| `C` | confirm-end | 선정 종료 (Phase 2) |

### 결과물 검토 단계

| 단축키 | 명령 | 설명 |
|--------|------|------|
| `A` | approve | 승인 |
| `M "<피드백>"` | revise | 수정 요청 |
| `D` | reject | 폐기 |
| `H` | hold | 보류 (Phase 3 집필 중) |

### 확인 단계 (전개 선정 확인)

| 단축키 | 명령 | 설명 |
|--------|------|------|
| `A` | approve | 승인 |
| `R` | reject | 돌아가기 |

한국어 자연어 입력도 동일하게 지원한다. (예: "2번", "승인", "다시 해줘")

---

## 시작 흐름 (Startup)

사용자가 소설 관련 요청을 하면 **반드시 먼저 신규/계속 여부를 확인**한다.

- **"새 소설 시작하자"** → 신규 작성: 장르/키워드 질문 → **한글 프로젝트명은 Write 도구로 UTF-8 파일(예: `projects/.initname.txt`)에 저장 후** `python nf.py init --title <디렉토리명> --name-file projects/.initname.txt` → 임시 파일 삭제 → Phase 1
  - 이유: Windows 셸(PowerShell 5.1/git-bash)이 비ASCII argv를 손실시키므로 한글명은 `--name-file` 필수. ASCII명이면 `init "<name>" --title <dir>`도 가능.
- **"이어서 쓰자"** → Glob `projects/*/state.json` → 프로젝트 선택 → `python nf.py status` → context/ 읽기 → 해당 단계 이어서 진행
- **원고 임포트** → 프로젝트 생성 → `python nf.py import-manuscript "<file>"` → Step 1-6
- **컨텍스트 임포트** → 프로젝트 생성 → `python nf.py import-context` → Phase 2 직행

---

## Workflow Architecture (4-Phase 순환 구조)

- **Phase 1** (최초 1회): 장르/키워드 → 방향성 5개 → PD 선정 → 기획안 → PD 승인 → context/ 6개 파일 생성
- **Phase 2**: 전개 옵션 5개 (Normal 2 / Moderate 1 / Rare 2) → PD 1개 선정
- **Phase 3**: 문체 설정 → 모드 선택 (auto/scene/episode, 상호 배타) → 집필
- **Phase 4**: 퇴고 → 원고 확정 → 복선 관리 → 컨텍스트 갱신 → Phase 2 복귀

---

## Phase별 AI 행동 가이드

> 각 Phase의 상세 스펙은 `NFC_plan.md` 참조. 여기서는 **AI가 실행할 CLI 명령 시퀀스**에 집중한다.

### Phase 1: 컨텍스트 수립

**Step 1-1 방향성 제안** (`direction_proposal`):
1. 장르/키워드 기반 방향성 5개 생성 (각 2~3줄)
2. `python nf.py add "방향성 N: 요약"` × 5 → `python nf.py next`
3. 사용자에게 제시: `[S]elect / [H]old / [D]iscard / [R]etry`

**Step 1-3 기획안** (`plan_buildup`):
1. 선정된 방향성 → 기획안 작성 (세계관, 캐릭터, 플롯 등)
2. `python nf.py save plan "drafts/plan_v1.md"` → `python nf.py next`
3. `[A]pprove / [M]odify / [D]ismiss`

**Step 1-5 컨텍스트 생성** (`context_creation`):
1. Write 도구로 context/ 6개 파일 직접 생성
2. `python nf.py next` → Phase 2

**Step 1-6 원고 분석** (`import_analysis`):
1. state.json의 import_file 읽기 → 원고 분석 → context/ 6개 파일 생성
2. `python nf.py save plan "drafts/import_analysis.md"` → `python nf.py next`

**Step 1-7 임포트 검토** (`import_review`):
- `[A]pprove` → Phase 2 / `[M]odify` → Step 1-6 / `[D]ismiss` → Step 1-1

---

### Phase 2: 전개 선정

**Step 2-1 전개 옵션** (`development_proposal`):
1. context/ 6개 + foreshadow.md 읽기 (최초 1회만)
2. 5개 전개 옵션 생성 (확률 분포 규칙 준수)
3. `python nf.py add "<text>전개</text><probability>0.XX</probability>" -p 0.XX` × 5
4. `python nf.py next`
5. 사용자에게 제시: `[S]elect <번호> (1개만) / [H]old / [D]iscard / [R]etry`

**Step 2-1 앙상블 모드 (v2.2, 선택)** — 여러 AI를 동원해 다양성 확보:
1. `python nf.py ensemble-dev` → 외부 CLI worker(기본 gemini-cli, codex-cli)가 **병렬**로 각각 전개안 3개(N1/M1/R1) 생성 → `drafts/ensemble_dev_*.md`에 저장
   - worker 지정: `ensemble-dev --workers gemini-cli,codex-cli,claude-cli`
2. Claude Code가 각 `drafts/ensemble_dev_*.md`를 읽고, **자체 전개안 배치도 추가 생성**
3. source(gemini/codex/claude)별로 모아 PD에게 **전체 제시** (어느 AI 안인지 태그)
4. PD가 고른 전개안만 `add`로 등록 → `select`로 확정 (이후 흐름은 동일)
   - 하이브리드 원칙: NF는 fan-out·저장만, 자기 배치·큐레이션은 Claude Code가 PD와 함께

**Step 2-3 전개 확인** (`development_confirm`):
- `[A]pprove` → Phase 3 / `[R]eject` → 전개 선정 복귀

---

### Phase 3: 집필

**Step 3-1 문체** (`style_setup`):
- 문체 질문 → `python nf.py config style_reference "<값>"` → `python nf.py next`

**Step 3-2 모드** (`mode_selection`):
- auto/scene/episode 중 택 1 (상호 배타)
- `python nf.py config writing_mode "scene|episode"` 또는 `python nf.py config auto_write "true"`
- `python nf.py next`

**Step 3-3 집필** (`writing`):

*Episode 모드*: context/ + foreshadow + 전개방향 참조 → 5,500자+ 작성 → `save manuscript "drafts/ep_draft.md"` → `next`
- `[A]pprove / [M]odify / [D]ismiss / [H]old` / `pd-proofread <file>`

*Scene 모드*: 장면 단위 작성 → `save manuscript "drafts/sc001.md"` → `next` → SCENE_DECISION
- 장면: `[A]pprove / [M]odify / [D]ismiss / merge-episode / scenes`
- 병합 후: `[A]pprove / [M]odify / [D]ismiss / [H]old` (5,500자 게이트)

*Auto 모드*: AI 내부 3화 자율 연쓰기 (전개생성→선택→집필→퇴고 반복)
- 3화 완성 후 `save manuscript` × 3 → `next` → PD 검토
- 선택 이력 테이블 첨부

*파이프라인 모드 (v2.3)*: 역할 분담형 릴레이 집필
1. `python nf.py draft-pipeline` → **자동**으로 2단계 실행:
   - 초고: **Gemini** — 전개+컨텍스트 기반 막 갈김(분량·기세 우선) → `episodes/ep###_making/01_draft_gemini.md`
   - 1차 퇴고: **Codex** — 맞춤법·오탈자·비문·설정 표기 오류 (라인 레벨) → `02_revise1_codex.md`
2. **2차 퇴고 + 승인은 Claude Code(라이브)**:
   - `02_revise1_codex.md` 읽기 → 컨텍스트 정합성(플롯/캐릭터/복선 충돌) 검수 → `03_revise2_claude.md` 저장
   - PD 제시: `[A]승인 / [M]수정 / [D]폐기` (M 시 `03_..._r2.md`로 버전 적층, 덮어쓰기 없음)
   - A → `episodes/ep###.md`로 승격 → Phase 4 컨텍스트 갱신
- 회차 번호는 `episode_count+1` 자동 (`ep001_making`, `ep002_making` …)
- 모든 단계가 `ep###_making/`에 **새 파일로 보존**되어 제작 히스토리가 남음
- worker 교체: `draft-pipeline --draft <type> --revise <type>`

*switch-auto*: 집필 중 `python nf.py switch-auto`로 auto 전환 가능

*과거 회차 재수정*: `python nf.py revise-episode ep001.md` (대부분의 단계에서 가능, 아래 "언제든 퇴고" 참조)

---

### Phase 4: 퇴고 및 컨텍스트 갱신

**Step 4-0**: `polishing/guideline.md` 확인 (없으면 PD에게 질문 후 생성)

**Step 4-1 퇴고** (`proofreading`):
1. 원고 + 가이드라인 참조 퇴고 (문체, 오탈자, 설정 충돌)
2. `save proofread "drafts/ep_proofread.md"` → `next`
3. `[A]pprove / [M]odify / [D]ismiss`

**Step 4-3 컨텍스트 갱신** (`context_update`):
1. Edit 도구로 context/ 파일 업데이트 (캐릭터, 세계관, 플롯, 테마, 톤, 컨셉)
2. 복선: foreshadow.md에 추가/삭제, payoff.md에 회수 기록
3. `python nf.py context-update` → `python nf.py next`

**Step 4-4 크기 점검**: 필요 시 `python nf.py context-backup` → 요약본 교체

**Step 4-5 완료**: `python nf.py next` → episodes/에 저장 → Phase 2 복귀

---

### 언제든 퇴고 (v2.1)

집필 도중 이전 회차를 수정해야 할 때, **Phase와 무관하게** 퇴고 모드에 진입할 수 있다.

**사용자 트리거**: "3화 퇴고하자", "ep003 수정해줘" 등

**퇴고 흐름**:
1. `python nf.py revise-episode ep003.md` → 퇴고 모드 진입
   - `drafts/revision_ep003.md` 생성 (원본 복사)
   - 현재 Phase/Step 저장 후 Phase 4 `proofread_decision`으로 전이
2. AI가 `drafts/revision_ep003.md`를 퇴고본으로 수정
3. PD 검토: `[A]pprove / [M]odify / [D]ismiss`
   - **A**: 승인 → `context_update` 단계
   - **M**: 수정 요청 → `proofreading` 단계로 이동하여 재퇴고
   - **D**: 폐기 → 원래 단계로 복귀 (변경 없음)
4. 컨텍스트 갱신 후 `next` → `episodes/ep003.md` 덮어쓰기 + 원래 단계로 복귀

**제약사항**: 다음 단계에서는 퇴고 진입 불가 (작업 완료 후 시도)
- `direction_decision` (방향성 선택 중)
- `plan_buildup` (기획안 작성 중)
- `writing` (집필 중)
- `proofreading` (퇴고 중)

---

## 재미/취향 학습 (v2.4, 토대)

LLM 라이터는 "재미"를 모른다 — 뻔한 전개를 고르거나 퇴고하며 재미 요소를 깎는다. 이를 보완하기 위해 **PD 결정 신호를 누적해 취향 프로파일로 distill하고 프롬프트에 되먹이는** 선호 조건화 레이어. (가중치 학습이 아님)

- **신호 자동 로깅**: `select`/`discard`/`hold`/`revise`/`pd_edit` → `taste/signals.jsonl` (마찰 0, 자동)
  - select는 고른 것 vs 버린 것 + 확률 분류(N/M/R)까지 기록 → "PD가 안전한 전개를 기피하는가" 같은 패턴의 원천
  - **PD 직접 편집 (v2.7)**: `pd-proofread` 등록 시 직전 AI 초안과 difflib 비교 → PD가 **뺀 줄/넣은 줄**을 `pd_edit` 신호로 기록 (말로 한 지시뿐 아니라 실제 손편집이 학습됨). reflection에서 가장 강한 신호로 취급
- **취향 프로파일**: `context/taste_profile.md` (init 시 웹소설 재미 원칙으로 시드)
  - base_agent가 **"PD 취향·재미 지침"** 헤딩으로 모든 에이전트 프롬프트에 주입 → 제안·집필·퇴고에 반영
  - '학습됨' 섹션(회피 패턴/살려야 할 요소/문체 선호)은 `taste-learn`이 갱신, 'PD 고정 지침'은 PD 수동
- **학습 루프** (`taste-learn` → `taste-apply`):
  1. `taste-learn`: 신호를 reflection worker(기본 gemini)가 정제 → `taste/profile_proposal.md` 갱신 제안 생성
  2. Claude Code가 제안 vs 현재 프로파일을 PD에게 제시 → 승인
  3. `taste-apply`: 이전 프로파일을 `backup/taste_profile_v{N}.md`로 백업 후 제안 적용
  - PD 고정 지침은 학습이 덮어쓰지 않음 (verbatim 보존)
- **AI 행동**: 전개 제안·집필·퇴고 시 이 프로파일의 재미 원칙과 회피 패턴을 의식적으로 반영한다. 가장 뻔한 선택을 경계하고, 호평받은 재미 요소는 퇴고에서 보존한다.
- **뻔함 가드 (v2.5)** `cliche-guard`: Phase 2에서 제안된 항목(PROPOSED)을 취향 프로파일 기준으로 채점(의외성/개연성/매력/뻔함). 신선·매력적인 안이 사실상 없으면 `too_safe` 경고 + 재생성 제안 → 김빠짐 방지. 워커(기본 codex-cli)가 채점하고 Claude Code가 PD에게 제시.
- **재미 보존 가드 (v2.6)** `fun-diff <before> <after>`: 초고(BEFORE) vs 퇴고본(AFTER)을 비교해, 초고의 재미 요소(인상적 대사·반전·감각 묘사·개성·목소리)가 퇴고에서 삭제·약화됐는지 검출하고 복원 제안. 단순 교정은 지적하지 않음. 손실 있으면 `regressed` 경고 → 퇴고 시 재미 감축 방지.
  - `draft-pipeline` 산출물에 직결: `fun-diff episodes/ep###_making/01_draft_gemini.md episodes/ep###_making/02_revise1_codex.md` (초고→1차퇴고 손실 점검). 2차 퇴고(Claude) 전후에도 적용 가능.

> 후속 계획: [전역 취향(작품 공통)은 작가 요청 시]

## 창작 규칙

### 전개 옵션 포맷

```
[N/M/R] 옵션 N.
<text>방향성 요약</text>
<probability>0.XX</probability>
```

### 확률 분포 (v1.5 3분류)

| 구분 | 개수 | probability | 설명 |
|------|------|-------------|------|
| [N]ormal | 2개 | > 0.30 | 자연스러운 전개 |
| [M]oderate | 1개 | 0.10~0.30 | 약간 의외 |
| [R]are | 2개 | < 0.10 | 독창적 (맥락 부합 필수) |

### 복선 규칙

- 생성: 집필 시 foreshadow.md에 기록
- 회수: foreshadow.md에서 삭제 → payoff.md에 기록
- 포맷: `NFC_plan.md` 참조

---

## CLI 명령 레퍼런스

`python nf.py <command>`

| 명령어 | 설명 |
|--------|------|
| `init <name> [--title <dir>]` | 새 프로젝트 생성 |
| `status` | 현재 상태 표시 |
| `items` | 항목 목록 (활성 항목만) |
| `add "<text>" [-p 0.XX]` | 항목 추가 |
| `select <id>` | 항목 선정 (1개) |
| `hold <id>` | 항목 보류 |
| `discard <id>` | 항목 폐기 |
| `retry` | 전체 폐기+재생성 |
| `approve` | 승인 |
| `revise "<feedback>"` | 수정 요청 |
| `reject` | 폐기→이전 단계 |
| `confirm-end` | 전개 선정 종료 (Phase 2) |
| `save <type> <file>` | 초안 저장 (plan/manuscript/proofread) |
| `config <key> <value>` | 설정 (style_reference/writing_mode/auto_write) |
| `context-update` | 컨텍스트 갱신 완료 |
| `context-backup` | 백업+압축 준비 |
| `backup-episode <file>` | 에피소드 파일 백업 |
| `char-count <file>` | 파일의 본문 글자 수 집계 |
| `next` | 다음 단계 |
| `import-manuscript <file>` | 원고 임포트 |
| `import-context` | 컨텍스트 임포트 |
| `pd-proofread <file>` | PD 퇴고 등록 (AI 퇴고 생략) |
| `switch-auto` | auto 모드 전환 |
| `merge-episode` | 장면 병합 (scene, 5,500자+) |
| `scenes` | 장면 목록 표시 |
| `revise-episode <file>` | v2.1: 언제든 퇴고 모드 진입 (episodes/ep###.md) |
| `ai-config` | v2.0: AI 프로바이더 설정 표시 |
| `ai-provider <type> -m <model> [--phase <phase>]` | v2.0: 프로바이더 설정 |
| `ai-validate` | v2.0: 프로바이더 설정 검증 |
| `ai-mode` | v2.0: standalone/passthrough 모드 확인 |
| `ai-cost` | v2.0: 토큰 사용량 요약 |
| `ai-cost-reset` | v2.0: 비용 추적 로그 초기화 |
| `ensemble-dev [--workers <list>]` | v2.2: Phase 2 앙상블 전개안 (외부 CLI 병렬, 기본 gemini-cli,codex-cli) |
| `draft-pipeline [--draft <t>] [--revise <t>]` | v2.3: 릴레이 집필 (Gemini 초고→Codex 1차퇴고 자동, 2차는 Claude) |
| `taste-init [--force]` | v2.4: 취향 프로파일 시드 (context/taste_profile.md) |
| `taste-learn [--worker <t>]` | v2.4: 신호 정제 → 프로파일 갱신 제안 (기본 gemini-cli) |
| `taste-apply` | v2.4: 갱신 제안을 프로파일에 적용 (이전 버전 backup/) |
| `cliche-guard [--worker <t>]` | v2.5: 제안 항목의 뻔함 심사 (취향 기준 채점, 기본 codex-cli) |
| `fun-diff <before> <after> [--worker <t>]` | v2.6: 초고 vs 퇴고본 재미 보존 검수 (손실 검출·복원 제안) |

---

## Key Rules

- **PD 중심**: AI는 제안, PD가 최종 판단
- **단축키**: A/M/D/S/H/R/C 또는 한국어 → CLI 명령 변환
- **컨텍스트 관리**: Phase 4에서 크기 부담 시 백업→요약 (PD 승인)
- **전개 포맷**: `<text>`, `<probability>` 태그 + 3분류 분포 필수
- **복선**: foreshadow.md/payoff.md 관리
- **퇴고 가이드라인**: polishing/guideline.md 참조
- **유연한 진입**: 원고/컨텍스트 임포트로 Phase 1 단축 가능
- **auto 전환**: 집필 중 언제든 switch-auto 가능
- **shelve**: hold 항목은 shelve/ 자동 저장
- **언제든 퇴고**: revise-episode로 언제든 퇴고 모드 진입 가능 (episode_count 불변)

## 프로젝트 디렉토리 구조

```
projects/{소설제목}/
├── state.json
├── ai_config.json       # v2.0: Phase별 AI 프로바이더 설정
├── cost_log.json        # v2.0: 토큰 사용량 로그
├── context/             # 6개 필수 + foreshadow.md, payoff.md (선택)
├── episodes/            # 완성 원고
├── drafts/              # 작업 중 초안
├── shelve/              # 보류 항목
├── polishing/guideline.md
└── backup/context_v{N}/
```
