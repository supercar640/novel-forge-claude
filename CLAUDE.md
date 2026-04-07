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

- **"새 소설 시작하자"** → 신규 작성: 장르/키워드 질문 → `python nf.py init "<프로젝트명>" --title <디렉토리명>` → Phase 1
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
2. **shelve/dev_*.md 파일 확인** → 보류된 전개가 있으면 읽기
3. 5개 전개 옵션 생성 (확률 분포 규칙 준수)
   - **보류된 전개 우선 포함**: shelve/에 보류된 전개가 있으면 해당 전개를 5개 중에 포함
   - 보류 전개의 probability는 기존 값 유지, 필요시 텍스트 다듬기 가능
   - 나머지 슬롯은 새로운 전개로 채움 (확률 분포 규칙 준수)
4. `python nf.py add "<text>전개</text><probability>0.XX</probability>" -p 0.XX` × 5
5. `python nf.py next`
6. 사용자에게 제시: `[S]elect <번호> (1개만) / [H]old / [D]iscard / [R]etry`

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
