# 만화 스토리보드 작성 모드 — 설계

- **작성일**: 2026-05-26
- **상태**: 설계 승인 대기
- **접근법**: A — `work_type` 필드 + 포맷 분기 (기존 4-Phase 상태머신 재사용)

## 1. 목표

Novel Factory는 현재 웹소설(산문) 전용이다. **Phase 1부터 작품 유형을 "만화"로 정하고 출발**하면, 기존 소설과 동일한 4-Phase 흐름(기획→전개→집필→퇴고)을 그대로 타되 **최종 산출물이 출판만화형 스토리보드(콘티)**가 되도록 한다.

핵심 의도: "novel과 비슷한 흐름, 산출물만 스토리보드". 별도 파이프라인을 새로 만들지 않고, 소설 모드의 상태머신·3집필모드(auto/scene/episode)·취향 학습 레이어(taste/cliche-guard/fun-diff)를 **공유**한다.

### 비목표 (YAGNI)

- 실제 작화/이미지 생성 (텍스트 콘티까지만)
- 만화 전용 별도 Phase/Step/에이전트 세트
- `page-count` 등 신규 분량 명령 (기존 `char-count` 분기로 흡수)
- 만화 전용 신규 컨텍스트 파일 (`tone.md` 섹션 확장으로 흡수)

## 2. 데이터 모델 변경 (`nf/models.py`)

### 2.1 `ProjectState.work_type`

```python
work_type: str = "novel"   # "novel" | "comic"
```

- `to_dict` / `from_dict`에 추가. `from_dict`는 `d.get("work_type", "novel")`로 읽어 **기존 state.json 하위 호환**(마이그레이션 불필요).

### 2.2 config 만화 키

`config`에 `comic_pages_per_episode` 추가 (기본 `18`).

- `_migrate_config`에 `config.setdefault("comic_pages_per_episode", 18)` 추가.
- 소설 프로젝트에서는 존재하되 사용되지 않음.

## 3. 작품 유형 결정 흐름 (`nf/cli.py`, `init`)

- `init` 파서에 `--type {novel,comic}` 플래그 추가 (기본 `novel`).
- `init` 핸들러에서 `work_type`을 state에 저장.
- 컨텍스트 시드(`taste-init` 및 Phase 1 컨텍스트 생성)는 `work_type`을 참조해 `tone.md`에 작화·연출 방향 섹션을 포함할지 결정.
- **CLAUDE.md 시작 흐름**: "새 소설/만화 시작하자" 분기에서 유형을 물어 `--type comic` 지정. 한글 프로젝트명은 기존 `--name-file` 규칙 그대로.

## 4. 분기 지점 — 정확히 3곳

상태머신 전이(`nf/state.py`), Phase 1/2/4 로직, 취향 학습 레이어는 **분기 없이 그대로** 동작한다. `work_type` 한 값으로 갈리는 곳은 아래 3곳뿐이다.

### 4.1 분량 집계/표시 (`nf/display.py`, `nf/fileops.py`)

- 소설: `count_story_chars` → `누적 N/5,500자` (현행 유지).
- 만화: `## P` 헤딩 수 집계 → `N/{comic_pages_per_episode}페이지 (총 M컷)`.
- `char-count` 명령은 `work_type==comic`이면 페이지/컷 집계로 분기 (신규 명령 추가 안 함).
- **게이트는 강제가 아니라 안내**다 (현행 소설과 동일). PD가 분량을 보고 판단한다.

### 4.2 집필 프롬프트 (`nf/prompts/`)

- 신규 `phase3_writing_comic.md` 작성 — 스토리보드 포맷 산출 지시 (§5 포맷 규칙 포함).
- `writing_agent`(및 orchestrator의 프롬프트 선택)가 `work_type`에 따라 `phase3_writing.md` ↔ `phase3_writing_comic.md`를 고른다.
- 퇴고(`phase4_revision.md`)는 공유하되, 만화일 때 "산문 문장"이 아니라 "컷 연출·대사·SFX"를 대상으로 본다는 단서를 조건부로 주입(프롬프트 내 분기 문구 또는 짧은 comic 변형 파일). 1차안은 조건부 문구 주입으로 충분.

### 4.3 컨텍스트 시드 (`tone.md`)

- 만화 프로젝트의 `tone.md`에 **"작화·연출 방향"** 섹션 추가: 화풍 톤(예: 극화체/명랑체), 컷 분할 밀도, 페이지당 평균 컷 수, 말풍선·SFX 표기 관례 등.
- 기존 6개 컨텍스트 파일 구성은 유지. 신규 파일 없음.

## 5. 스토리보드 마크다운 포맷 (확정)

출판만화형: 페이지 단위로 묶고, 한 페이지에 여러 컷을 배치한다.

```markdown
# ep001 스토리보드 (목표 18p)

## P1

### Cut 1
- **구도/카메라**: 와이드 부감 — 비 내리는 새벽 도시 전경
- **연출**: 네온 반사, 적막. 인물 없음(상황 제시)
- **나레이션**: 도시는 잠들지 않는다.
- **대사**: —
- **SFX**: 후두둑

### Cut 2
- **구도/카메라**: 클로즈업 — 주인공의 젖은 눈
- **연출**: 빗물과 눈물 대비
- **나레이션**: —
- **대사**: (료) "…늦었나."
- **SFX**: —

## P2 [3단 분할]

### Cut 1
...
```

### 포맷 규칙

- **페이지** = `## P{n}` 헤딩. **컷** = `### Cut {n}` 헤딩.
- **분량 카운트**: `## P` 헤딩 수 = 페이지 수, `### Cut` 헤딩 수 = 총 컷 수 (정규식 집계).
- **컷 필드 5종 고정**: `구도/카메라` · `연출` · `나레이션` · `대사` · `SFX`. 해당 없으면 `—`로 명시(누락과 구분).
- **대사 형식**: `(화자) "내용"` — 추후 캐릭터별 대사량 분석·취향 학습 재활용 가능.
- **페이지 컷 배치 힌트**(선택): `## P3 [3단 분할]`처럼 헤딩 옆 대괄호.
- **파일 경로**: 소설과 동일. 승인본 `episodes/ep###.md`, 제작 히스토리 `episodes/ep###_making/`. 확장자·경로 규칙 그대로 재사용.

## 6. CLI · 문서 변경

- `init --type {novel,comic}` (§3).
- `char-count` 분기 (§4.1).
- `status`/`display`에 `work_type` 및 만화 분량 표시 반영.
- 문서 동기화: `CLAUDE.md`(시작 흐름 + 만화 포맷 규칙), `README.md`(작품 유형 개념 + `--type` 플래그 + 스토리보드 포맷), 필요 시 `AGENTS.md`(새 분기 지점 안내).

## 7. 영향 범위 / 하위 호환

- 기존 소설 프로젝트: `work_type` 미존재 → `"novel"`로 로드. **동작 변화 없음**.
- 신규 필드/키는 모두 추가형 → state.json 스키마 호환.
- 취향 학습·앙상블·파이프라인: `work_type` 무관하게 동작 (만화 콘티도 텍스트라 동일 신호 로깅 가능).

## 8. 수동 검증 (테스트 스위트 없음)

1. `python -c "import nf.cli, nf.state, nf.models"` — import 무결성.
2. `python nf.py init comic_test --type comic` → `state.json`에 `work_type:"comic"` 확인.
3. Phase 3까지 진행 → 스토리보드 포맷 산출 확인 → `char-count`가 `N/18페이지 (총 M컷)` 표시 확인.
4. 기존 소설 프로젝트 `status` → 동작·표시 변화 없음 확인 (회귀).
5. 검증용 임시 프로젝트는 정리.
