# AGENTS.md

이 파일은 **이 저장소의 코드를 수정하는 AI 코딩 에이전트**(Codex, Cursor, Gemini CLI, Claude Code 등)를 위한 작업 지침이다. 사람 협업자에게는 `README.md`, Claude Code 전용 행동 매뉴얼은 `CLAUDE.md`를 참조한다.

> **혼동 주의**: 이 프로젝트는 실행 중 외부 CLI 에이전트(gemini/codex/claude)를 *워커*로 동원한다(앙상블·릴레이 집필). 그 워커들의 역할은 `README.md`·`CLAUDE.md`에 정의돼 있다. **이 AGENTS.md는 그 런타임 워커가 아니라, NF 자체의 소스 코드를 고치는 에이전트를 위한 것이다.**

---

## 프로젝트 한눈에

- **무엇**: PD와 AI가 협업해 웹소설을 기획·집필하는 인터랙티브 CLI 도구 (Novel Factory, NF v2.7)
- **핵심 원칙**: CLI(`python nf.py <cmd>`)는 **상태 관리 도구**다. 콘텐츠 생성은 standalone 모드(NF가 직접 AI API 호출) 또는 passthrough 모드(외부 AI가 생성)에서 이뤄진다.
- **언어/런타임**: Python 3.10+, 표준 라이브러리 중심. AI 프로바이더 SDK(`anthropic`/`openai`/`google-generativeai`)는 **선택적**으로만 import한다.
- **상태**: 모든 작업 상태는 `projects/{제목}/state.json`에 직렬화된다. 상태 머신은 `nf/state.py`, 데이터 모델은 `nf/models.py`.

---

## 셋업 · 실행 · 검증

### 셋업
```bash
# 외부 의존성 없이 동작하는 부분이 대부분. AI 호출이 필요할 때만 설치:
pip install anthropic            # 또는 openai / google-generativeai
```
`requirements.txt`·`pyproject.toml`은 **없다**. 표준 라이브러리로 import 가능해야 하며, 프로바이더 SDK는 함수 안에서 lazy import 하거나 누락 시 친절히 실패하도록 둔다.

### 실행
```bash
python nf.py                # 인자 없음 → 대화형 REPL (nf/interactive.py)
python nf.py <command> ...  # 단발 명령 (nf/cli.py)
python nfc.py <command>     # 하위 호환 래퍼 — 동일하게 동작해야 함
```

### 검증 (자동 테스트 없음)
이 저장소에는 **테스트 스위트가 없다.** 변경 후에는 다음으로 수동 검증한다.

```bash
# 1) import/문법 깨짐 점검
python -c "import nf.cli, nf.state, nf.models"

# 2) 명령 라우팅 점검 (실데이터 건드리지 말 것)
python nf.py --help
python nf.py status --project <임시-테스트-프로젝트>
```
- **실제 `projects/` 데이터로 검증하지 말 것.** 필요하면 `python nf.py init <임시명>`으로 일회용 프로젝트를 만들어 검증하고 정리한다.
- 변경한 명령 경로는 실제로 한 번 실행해 출력으로 확인한다 ("아마 될 것"으로 끝내지 않는다).

---

## 코드 구조

```
nf.py / nfc.py          엔트리포인트 (UTF-8 stdout 래핑 + REPL/CLI 분기)
nf/
├── models.py           데이터 모델 (Phase, Step, Item, ProjectState)
├── state.py            상태 머신 — 전이/검증/실행의 핵심
├── cli.py              argparse 기반 명령 등록 + 디스패치
├── interactive.py      대화형 REPL
├── fileops.py          프로젝트 파일시스템 I/O
├── display.py          출력 포매팅
├── config.py           프로젝트별 AI 설정 (ai_config.json)
├── orchestrator.py     Phase ↔ 에이전트 연결
├── cost_tracker.py     토큰/비용 추적
├── ensemble.py         v2.2 앙상블 전개안 fan-out
├── pipeline.py         v2.3 릴레이 집필 + v2.8 작가실 릴레이(draft-room)
├── taste.py            v2.4 취향 신호 로깅 + 프로파일 시드
├── taste_learn.py      v2.4 신호 정제 → 갱신 제안
├── cliche_guard.py     v2.5 뻔함 가드
├── fun_diff.py         v2.6 재미 보존 가드
├── pd_edit.py          v2.7 PD 손편집 diff → pd_edit 신호
├── providers/          AI 프로바이더 추상화 (HTTP API + CLI subprocess)
├── agents/             Phase별 에이전트 (planning/development/writing/revision)
└── prompts/            Phase별 프롬프트 템플릿 (*.md)
```

### 새 CLI 명령을 추가할 때
명령 하나를 추가/변경하려면 **두 곳을 같이** 수정해야 한다 (`nf/cli.py`):
1. **등록**: `sub.add_parser("<cmd>", help=...)` (필요 시 인자 추가)
2. **디스패치**: `main()`의 `elif args.command == "<cmd>":` 분기

그리고 사용자 문서 3개를 동기화한다:
- `CLAUDE.md` — CLI 명령 레퍼런스 표
- `README.md` — CLI 명령어 표
- (이 파일은 구조가 바뀔 때만)

새 프로바이더는 `nf/providers/base.py`(또는 CLI 계열은 `cli_base.py`)를 상속하고 `nf/providers/__init__.py`에 등록한다.

### work_type 분기 (소설/만화)

`ProjectState.work_type`("novel"|"comic")이 산출물 종류를 가른다. 분량 집계/표시/게이트, 집필 프롬프트, `tone.md` 시드 3축에서만 분기하고 상태머신·전이는 공유한다. 분량 분기는 `work_type=="comic"`을 먼저 확인하고, 아니면 기존 `webnovel` 글자 로직으로 폴백한다. 페이지/컷 집계는 `ProjectFiles.count_pages` / `count_cuts`를 쓴다.

---

## 코딩 컨벤션

- **인코딩**: 모든 `.py` 첫 줄은 `# -*- coding: utf-8 -*-`. 소스·산출물 모두 UTF-8. 콘텐츠는 거의 항상 한국어다.
- **새 의존성 추가 금지(원칙)**: 표준 라이브러리로 해결한다. 외부 패키지가 꼭 필요하면 lazy import + 누락 시 명확한 에러 메시지로 격리한다.
- **기존 스타일 따르기**: 주변 파일의 네이밍·주석 밀도·관용구에 맞춘다. 대규모 리포맷 금지.
- **외과적 변경**: 요청 범위만 고친다. 무관한 리팩터링·정리를 끼워 넣지 않는다.
- **상태 직렬화 호환**: `models.py`/`state.json` 스키마를 바꾸면 기존 `projects/*/state.json`을 깨뜨릴 수 있다. 필드는 가급적 추가만 하고, 로드 시 기본값으로 하위 호환을 보장한다.

---

## 플랫폼 주의 (Windows)

주 개발 환경은 **Windows 10 + PowerShell 5.1**이다.

- **stdout/stderr UTF-8 래핑**: `nf.py`가 시작 시 강제한다. 직접 `print` 대신 기존 출력 경로(`display.py`)를 쓴다.
- **한글 argv 손실**: PowerShell/git-bash가 비ASCII argv를 손상시킨다. 한글 입력이 명령행 인자로 들어와야 하면 **파일 경유**(`--name-file` 패턴, `init` 참조)로 받는다. 새 명령에서 한글을 직접 argv로 받지 말 것.
- **경로**: `pathlib.Path`를 쓴다. 하드코딩된 `/` 구분자 금지.

---

## Git 워크플로 (엄수)

- **로컬 머지 금지.** `git merge`로 브랜치를 로컬 통합하지 않는다. 통합은 GitHub PR로만. (과거 로컬 머지 후 미푸시 상태에서 다른 머신과 충돌한 이력 있음.)
- 커밋/푸시는 **요청받았을 때만** 한다. `main`에서 직접 작업하지 말고 브랜치를 먼저 판다.
- 커밋 메시지는 기존 컨벤션을 따른다: `feat: <한국어 요약> (vX.Y)`.
- 훅 우회(`--no-verify`)·강제 푸시는 명시 요청 없이 하지 않는다.

---

## 절대 건드리지 말 것

- **`projects/`** — 사용자 소설 데이터. `.gitignore` 대상. 읽기는 가능하나 임의 수정/삭제 금지. 검증은 일회용 임시 프로젝트로.
- **`ideas/`** — 사용자 아이디어 메모. `.gitignore` 대상.
- **`.claude/`** — 로컬 에이전트 설정. `.gitignore` 대상.
- `state.json`을 손으로 편집하지 말 것 — 상태 전이는 CLI 명령으로만 일어나야 한다.

---

## 참고 문서

| 문서 | 용도 |
|------|------|
| `README.md` | 사용자용 개요·설치·CLI 레퍼런스 |
| `CLAUDE.md` | Claude Code 전용 행동 매뉴얼(워크플로·단축키·런타임 워커 역할) |
| `AI_GUIDE.md` | 모델 무관 범용 AI 가이드 |
| `NF_v2.0_plan.md` | v2.0 업그레이드 계획서 |
| `NFC_plan.md` | 상세 스펙(포맷·복선 규칙 등) |
