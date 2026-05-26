# 만화 스토리보드 작성 모드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1에서 작품 유형을 "만화"로 정하면 기존 4-Phase 흐름을 그대로 타되 산출물이 출판만화형 스토리보드(페이지/컷 콘티)가 되도록 한다.

**Architecture:** `ProjectState.work_type` 한 필드("novel"|"comic")로 분기. 상태머신·전이·취향 학습은 공유하고, 분량 집계/표시/게이트, 집필 프롬프트, 컨텍스트 시드 3축만 갈라준다. 기존 `webnovel` 분량 플래그 패턴과 정합하게 처리.

**Tech Stack:** Python 3.10+ 표준 라이브러리. 테스트 스위트·외부 의존성 없음 → 검증은 `python -c` import 무결성 + 임시 프로젝트 e2e + 기존 소설 프로젝트 회귀 확인.

**참고 스펙:** `docs/superpowers/specs/2026-05-26-comic-storyboard-mode-design.md`

---

## 파일 구조

| 파일 | 책임 | 변경 |
|------|------|------|
| `nf/models.py` | `ProjectState` 직렬화 + config 마이그레이션 | work_type 필드 + comic 키 |
| `nf/fileops.py` | 프로젝트 생성 + 본문 집계 헬퍼 | create_project 인자 + count_pages/count_cuts |
| `nf/cli.py` | init 파서/핸들러, char-count, merge 게이트 | --type, work_type 전파, 분량 분기 |
| `nf/state.py` | config set 검증 | work_type/comic_pages 키 허용 |
| `nf/display.py` | scene 분량 표시 | work_type 분기 |
| `nf/interactive.py` | scene merge 게이트 | work_type 분기 |
| `nf/prompts/phase3_writing_comic.md` | 만화 집필 프롬프트 (standalone용) | 신규 |
| `CLAUDE.md` / `README.md` / `AGENTS.md` | 문서 | 만화 모드 반영 |

---

## 사전 확인 (현황 사실)

- `MIN_STORY_CHARS = 5700` (`cli.py:167`) — 게이트 상수. 표시 문구는 "5,500자"로 불일치하나 **기존 동작 유지**(이번 작업에서 건드리지 않음).
- `webnovel` config 플래그(기본 True)가 분량 체크 on/off로 이미 쓰임: `display.py:156`, `interactive.py:241/255`, `cli.py:704/654`, `state.py:405-412`.
- 만화 분기는 `webnovel`과 **독립**이다. 우선순위: `work_type=="comic"`이면 페이지 기준, 아니면 기존 `webnovel` 글자 로직 그대로.
- `inject_char_count`는 이미 비활성(표기 제거만) → 만화 분기 불필요.

---

## Task 1: 데이터 모델 — work_type 필드 + comic config 키

**Files:**
- Modify: `nf/models.py` (ProjectState dataclass `:77-87`, to_dict `:97-116`, from_dict `:118-139`, _migrate_config `:148-159`)

- [ ] **Step 1: work_type 필드 추가**

`nf/models.py` ProjectState의 `selected_developments` 아래(`:86` 다음)에 추가:

```python
    work_type: str = "novel"  # "novel" | "comic"
```

- [ ] **Step 2: to_dict에 직렬화 추가**

`to_dict`의 `"selected_developments": self.selected_developments,` 줄 다음에 추가:

```python
            "work_type": self.work_type,
```

- [ ] **Step 3: from_dict에 역직렬화 추가 (하위 호환)**

`from_dict`의 `selected_developments=d.get("selected_developments", []),` 줄 다음에 추가:

```python
            work_type=d.get("work_type", "novel"),
```

- [ ] **Step 4: comic config 키 마이그레이션**

`_migrate_config`의 `if "auto_write" not in config:` 블록 다음, `return config` 앞에 추가:

```python
        config.setdefault("comic_pages_per_episode", 18)
```

- [ ] **Step 5: import 무결성 + 직렬화 왕복 검증**

Run:
```bash
python -c "from nf.models import ProjectState; s=ProjectState('p','t',work_type='comic'); d=s.to_dict(); s2=ProjectState.from_dict(d); assert s2.work_type=='comic'; assert s2.config['comic_pages_per_episode']==18; old=ProjectState.from_dict({'project_name':'p','novel_title':'t'}); assert old.work_type=='novel'; print('OK')"
```
Expected: `OK` (신규 work_type 왕복 + 기존 state.json 하위 호환 확인)

- [ ] **Step 6: Commit**

```bash
git add nf/models.py
git commit -m "feat(comic): ProjectState.work_type + comic_pages_per_episode config"
```

---

## Task 2: config set으로 work_type / comic_pages 변경 허용

**Files:**
- Modify: `nf/state.py` (`set_config` 분기 `:405-412`)

- [ ] **Step 1: 현재 분기 확인**

`nf/state.py:405-412`는 `webnovel` 키와 미지원 키 에러를 처리한다. `work_type`/`comic_pages_per_episode`를 명시 허용해야 한다.

- [ ] **Step 2: work_type 분기 추가**

`if key == "webnovel":` 블록 **앞**에 추가:

```python
        if key == "work_type":
            if value not in ("novel", "comic"):
                return state, display.error("work_type은 'novel' 또는 'comic'만 가능합니다.")
            state.work_type = value
            return state, display.ok(f"work_type = {value}")
        if key == "comic_pages_per_episode":
            try:
                n = int(value)
            except ValueError:
                return state, display.error("comic_pages_per_episode는 정수여야 합니다.")
            state.config["comic_pages_per_episode"] = n
            return state, display.ok(f"comic_pages_per_episode = {n}")
```

- [ ] **Step 3: 미지원 키 에러 메시지에 신규 키 추가**

`:412`의 에러 메시지 문자열을 다음으로 교체:

```python
            return state, display.error(f"알 수 없는 설정 키: {key}. 사용 가능: style_reference, writing_mode, auto_write, webnovel, mode, work_type, comic_pages_per_episode")
```

- [ ] **Step 4: import 검증**

Run: `python -c "import nf.state; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add nf/state.py
git commit -m "feat(comic): config set supports work_type, comic_pages_per_episode"
```

---

## Task 3: init --type 플래그 + create_project 전파

**Files:**
- Modify: `nf/cli.py` (init 파서 `:25-30`, handle_init `:419-457`)
- Modify: `nf/fileops.py` (create_project `:101-118`)

- [ ] **Step 1: create_project에 work_type 파라미터 추가**

`nf/fileops.py:101` 시그니처를 교체:

```python
    def create_project(cls, base_dir: Path, project_name: str, novel_title: str, work_type: str = "novel") -> ProjectFiles:
```

그리고 `:115`의 ProjectState 생성을 교체:

```python
        state = ProjectState(project_name=project_name, novel_title=novel_title, work_type=work_type)
```

- [ ] **Step 2: init 파서에 --type 추가**

`nf/cli.py:30` (`--name-file` add_argument 다음)에 추가:

```python
    p_init.add_argument("--type", dest="work_type", choices=["novel", "comic"], default="novel",
                        help="작품 유형 (novel=웹소설, comic=만화 스토리보드)")
```

- [ ] **Step 3: handle_init에서 work_type 전파**

`nf/cli.py:449`의 create_project 호출을 교체:

```python
        pf = ProjectFiles.create_project(base_dir, name, title, work_type=getattr(args, "work_type", "novel"))
```

그리고 `:452` 성공 메시지 다음에 만화 안내 추가:

```python
        if getattr(args, "work_type", "novel") == "comic":
            print(display.step_msg("작품 유형: 만화 스토리보드 (산출물=페이지/컷 콘티)"))
```

- [ ] **Step 4: e2e 검증 (임시 프로젝트)**

Run:
```bash
python nf.py init comic_e2e --type comic
python -c "import json; d=json.load(open('projects/comic_e2e/state.json',encoding='utf-8')); assert d['work_type']=='comic'; assert d['config']['comic_pages_per_episode']==18; print('OK')"
```
Expected: 프로젝트 생성 메시지 + 만화 안내 + `OK`

- [ ] **Step 5: 정리**

Run: `python -c "import shutil; shutil.rmtree('projects/comic_e2e')"`

- [ ] **Step 6: Commit**

```bash
git add nf/cli.py nf/fileops.py
git commit -m "feat(comic): init --type flag propagates work_type to project"
```

---

## Task 4: 페이지/컷 카운트 헬퍼

**Files:**
- Modify: `nf/fileops.py` (count_story_chars 옆 `:261-278`)

- [ ] **Step 1: count_pages / count_cuts 추가**

`nf/fileops.py`의 `count_story_chars` staticmethod **다음**에 추가:

```python
    @staticmethod
    def count_pages(text: str) -> int:
        """만화 스토리보드의 페이지 수 집계 ('## P' 헤딩)."""
        import re
        return len(re.findall(r"(?m)^##\s+P\d+", text))

    @staticmethod
    def count_cuts(text: str) -> int:
        """만화 스토리보드의 총 컷 수 집계 ('### Cut' 헤딩)."""
        import re
        return len(re.findall(r"(?m)^###\s+Cut\s+\d+", text))
```

- [ ] **Step 2: 카운트 정확성 검증**

Run:
```bash
python -c "from nf.fileops import ProjectFiles as P; t='# ep001\n\n## P1\n### Cut 1\n- a\n### Cut 2\n\n## P2 [3단 분할]\n### Cut 1\n'; assert P.count_pages(t)==2, P.count_pages(t); assert P.count_cuts(t)==3, P.count_cuts(t); print('OK')"
```
Expected: `OK` (페이지 2, 컷 3 — 대괄호 배치 힌트가 붙은 헤딩도 집계)

- [ ] **Step 3: Commit**

```bash
git add nf/fileops.py
git commit -m "feat(comic): count_pages / count_cuts storyboard helpers"
```

---

## Task 5: 분량 표시·게이트 work_type 분기

**Files:**
- Modify: `nf/cli.py` (handle_char_count `:693-712`, merge 게이트 `:653-654`)
- Modify: `nf/display.py` (format_scenes `:156-159`)
- Modify: `nf/interactive.py` (merge 게이트 `:240-256`)

- [ ] **Step 1: char-count 만화 분기 (`cli.py`)**

`handle_char_count`(`:702` 이후)에서 `text = ...read_text(...)` 다음, `char_count = ...` 분기를 교체. 기존:

```python
    char_count = ProjectFiles.count_story_chars(text)
    webnovel = state.config.get("webnovel", True)
    if webnovel:
```

를 다음으로 교체 (만화 분기를 맨 앞에):

```python
    if state.work_type == "comic":
        pages = ProjectFiles.count_pages(text)
        cuts = ProjectFiles.count_cuts(text)
        target = state.config.get("comic_pages_per_episode", 18)
        if pages >= target:
            print(display.ok(f"{filepath.name}: {pages}/{target}페이지 (총 {cuts}컷, 기준 충족)"))
        else:
            print(display.error(f"{filepath.name}: {pages}/{target}페이지 (총 {cuts}컷, {target - pages}페이지 부족)"))
        return
    char_count = ProjectFiles.count_story_chars(text)
    webnovel = state.config.get("webnovel", True)
    if webnovel:
```

- [ ] **Step 2: format_scenes 만화 분기 (`display.py`)**

`nf/display.py:135` `format_scenes` 안에서, 컷/페이지 합산을 위해 루프 직전 분기를 추가한다. `:156-159`의 누적 표시 블록을 교체. 기존:

```python
    if state.config.get("webnovel", True):
        lines.append(f"  누적: {total_chars:,}/5,500자")
    else:
        lines.append(f"  누적: {total_chars:,}자")
    return "\n".join(lines)
```

를:

```python
    if state.work_type == "comic":
        total_pages = sum(
            ProjectFiles.count_pages((pf.root / sf).read_text(encoding="utf-8"))
            for sf in scene_files if (pf.root / sf).exists()
        )
        total_cuts = sum(
            ProjectFiles.count_cuts((pf.root / sf).read_text(encoding="utf-8"))
            for sf in scene_files if (pf.root / sf).exists()
        )
        target = state.config.get("comic_pages_per_episode", 18)
        lines.append(f"  누적: {total_pages}/{target}페이지 (총 {total_cuts}컷)")
    elif state.config.get("webnovel", True):
        lines.append(f"  누적: {total_chars:,}/5,500자")
    else:
        lines.append(f"  누적: {total_chars:,}자")
    return "\n".join(lines)
```

> 참고: 만화 분기에서 `char_count` 라벨(글자 수)은 줄별 표시로 남지만 누적은 페이지/컷으로 표기한다. 줄별 라벨까지 바꾸는 것은 YAGNI로 보류.

- [ ] **Step 3: scene merge 게이트 + 결과 표시 만화 분기 (`interactive.py`)**

`nf/interactive.py`의 게이트 함수는 루프 변수 `sf`, 경로 `pf.root / sf`, 모듈 별칭 `_PF`를 쓴다. 두 곳을 수정한다.

(a) 게이트 `:241`을 교체. 기존:

```python
        if state.config.get("webnovel", True) and total_chars < 5500:
            print(display.error(
                f"병합 불가: 누적 {total_chars:,}자 / 최소 5,500자. "
                f"{5500 - total_chars:,}자 추가 필요. 장면을 더 작성하세요."
            ))
            return state
```

를:

```python
        if state.work_type == "comic":
            total_pages = sum(
                _PF.count_pages((pf.root / sf).read_text(encoding="utf-8"))
                for sf in scene_files if (pf.root / sf).exists()
            )
            target = state.config.get("comic_pages_per_episode", 18)
            if total_pages < target:
                print(display.error(
                    f"병합 불가: 누적 {total_pages}/{target}페이지. "
                    f"{target - total_pages}페이지 추가 필요. 장면을 더 작성하세요."
                ))
                return state
        elif state.config.get("webnovel", True) and total_chars < 5500:
            print(display.error(
                f"병합 불가: 누적 {total_chars:,}자 / 최소 5,500자. "
                f"{5500 - total_chars:,}자 추가 필요. 장면을 더 작성하세요."
            ))
            return state
```

(b) 병합 결과 표시 `:254-258`을 교체. 기존:

```python
        char_count = _PF.count_story_chars(text)
        if state.config.get("webnovel", True):
            print(display.ok(f"병합 결과: {char_count:,}자 (기준: 5,500자)"))
        else:
            print(display.ok(f"병합 결과: {char_count:,}자"))
```

를:

```python
        if state.work_type == "comic":
            pages = _PF.count_pages(text)
            cuts = _PF.count_cuts(text)
            target = state.config.get("comic_pages_per_episode", 18)
            print(display.ok(f"병합 결과: {pages}/{target}페이지 (총 {cuts}컷)"))
        else:
            char_count = _PF.count_story_chars(text)
            if state.config.get("webnovel", True):
                print(display.ok(f"병합 결과: {char_count:,}자 (기준: 5,500자)"))
            else:
                print(display.ok(f"병합 결과: {char_count:,}자"))
```

- [ ] **Step 4: cli.py merge 게이트 + 결과 표시 만화 분기**

`nf/cli.py`의 merge 게이트 함수는 루프 변수 `sf`, 경로 `pf.root / sf`, 별칭 `ProjectFiles`를 쓴다. 두 곳을 수정한다.

(a) 게이트 `:654-659`를 교체. 기존:

```python
    if state.config.get("webnovel", True) and total_chars < MIN_STORY_CHARS:
        print(display.error(
            f"병합 불가: 누적 {total_chars:,}자 / 최소 {MIN_STORY_CHARS:,}자. "
            f"{MIN_STORY_CHARS - total_chars:,}자 추가 필요. 장면을 더 작성하세요."
        ))
        sys.exit(1)
```

를:

```python
    if state.work_type == "comic":
        total_pages = sum(
            ProjectFiles.count_pages((pf.root / sf).read_text(encoding="utf-8"))
            for sf in scene_files if (pf.root / sf).exists()
        )
        target = state.config.get("comic_pages_per_episode", 18)
        if total_pages < target:
            print(display.error(f"병합 불가: 누적 {total_pages}/{target}페이지. {target - total_pages}페이지 부족."))
            sys.exit(1)
    elif state.config.get("webnovel", True) and total_chars < MIN_STORY_CHARS:
        print(display.error(
            f"병합 불가: 누적 {total_chars:,}자 / 최소 {MIN_STORY_CHARS:,}자. "
            f"{MIN_STORY_CHARS - total_chars:,}자 추가 필요. 장면을 더 작성하세요."
        ))
        sys.exit(1)
```

(b) 병합 결과 표시 `:667-669`(및 그 else)를 만화 분기로 감싼다. 기존:

```python
    char_count = ProjectFiles.count_story_chars(text)
    if state.config.get("webnovel", True):
        print(display.ok(f"병합 결과: {char_count:,}자 (기준: {MIN_STORY_CHARS:,}자)"))
```

직전에 만화 분기를 추가하고 기존 글자 표시는 else로 보낸다:

```python
    if state.work_type == "comic":
        pages = ProjectFiles.count_pages(text)
        cuts = ProjectFiles.count_cuts(text)
        target = state.config.get("comic_pages_per_episode", 18)
        print(display.ok(f"병합 결과: {pages}/{target}페이지 (총 {cuts}컷)"))
    else:
        char_count = ProjectFiles.count_story_chars(text)
        if state.config.get("webnovel", True):
            print(display.ok(f"병합 결과: {char_count:,}자 (기준: {MIN_STORY_CHARS:,}자)"))
```

> 주의: 위 (b)에서 기존 `webnovel` else 절(`{char_count:,}자`)이 그 아래에 있으면 그대로 둔다 — 새 `else` 블록 안에 자연스럽게 포함되도록 들여쓰기를 맞춘다.

- [ ] **Step 5: e2e 검증 — 만화 char-count**

Run:
```bash
python nf.py init comic_gate --type comic
python -c "open('projects/comic_gate/drafts/sc001.md','w',encoding='utf-8').write('# sc\n' + ''.join(f'## P{i}\n### Cut 1\n### Cut 2\n' for i in range(1,20)))"
python nf.py char-count drafts/sc001.md --project comic_gate
```
Expected: `19/18페이지 (총 38컷, 기준 충족)` 류 메시지

- [ ] **Step 6: 회귀 검증 — 소설 char-count 불변**

Run:
```bash
python nf.py init novel_reg
python -c "open('projects/novel_reg/drafts/sc001.md','w',encoding='utf-8').write('가'*100)"
python nf.py char-count drafts/sc001.md --project novel_reg
```
Expected: `100자` 기반 기존 글자 메시지(만화 메시지 아님) — 소설 경로 회귀 없음 확인

- [ ] **Step 7: 정리**

Run: `python -c "import shutil; shutil.rmtree('projects/comic_gate'); shutil.rmtree('projects/novel_reg')"`

- [ ] **Step 8: Commit**

```bash
git add nf/cli.py nf/display.py nf/interactive.py
git commit -m "feat(comic): page/cut 기반 분량 표시·병합 게이트 분기"
```

---

## Task 6: 만화 집필 프롬프트 (standalone 템플릿)

**Files:**
- Create: `nf/prompts/phase3_writing_comic.md`

- [ ] **Step 1: 만화 집필 프롬프트 작성**

`nf/prompts/phase3_writing_comic.md` 생성:

```markdown
# Phase 3: 만화 스토리보드 집필

당신은 출판만화(단행본/주간지형) 콘티 작가입니다. 선정된 전개와 컨텍스트를 바탕으로 **페이지/컷 단위 스토리보드**를 작성합니다. 산문 소설이 아니라 작화 지시·연출 콘티입니다.

## 산출 포맷 (엄수)

- 페이지: `## P{n}` 헤딩
- 컷: `### Cut {n}` 헤딩
- 각 컷은 아래 5개 필드를 **항상** 포함. 해당 없으면 `—`로 명시:
  - **구도/카메라**: 샷 크기·앵글·구도 (예: 와이드 부감, 클로즈업)
  - **연출**: 분위기·연출 의도·시각 효과
  - **나레이션**: 나레이션 박스 텍스트
  - **대사**: `(화자) "내용"` 형식. 여러 명이면 줄바꿈으로 나열
  - **SFX**: 효과음·의성어
- 페이지 컷 배치 힌트가 있으면 `## P3 [3단 분할]`처럼 헤딩 옆 대괄호로 표기(선택).

## 분량

- 목표: `comic_pages_per_episode` 페이지(기본 18p). 페이지 수로 분량을 맞춥니다.
- 컷 밀도는 `tone.md`의 작화·연출 방향을 따릅니다.

## 예시

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

## 규칙

- 복선은 `foreshadow.md`에 매설/회수 기록 (소설과 동일).
- 취향 프로파일(`context/taste_profile.md`)의 재미 원칙·회피 패턴을 반영합니다.
```

- [ ] **Step 2: 파일 생성 확인**

Run: `python -c "import pathlib; assert pathlib.Path('nf/prompts/phase3_writing_comic.md').exists(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nf/prompts/phase3_writing_comic.md
git commit -m "feat(comic): standalone 만화 스토리보드 집필 프롬프트"
```

> **후속(이번 범위 밖, YAGNI):** standalone orchestrator(`nf/orchestrator.py`)가 `work_type=="comic"`일 때 이 프롬프트를 자동 로드하도록 `WritingAgent` 생성부를 분기. 현재 실사용 경로는 passthrough(Claude Code 집필)이며, 그 경로는 CLAUDE.md 지시(Task 7)로 커버된다.

---

## Task 7: 문서 동기화

**Files:**
- Modify: `CLAUDE.md` (시작 흐름 + Phase 3 + 창작 규칙)
- Modify: `README.md` (작품 유형 개념 + --type)
- Modify: `AGENTS.md` (work_type 분기 안내)

- [ ] **Step 1: CLAUDE.md 시작 흐름에 만화 분기 추가**

`CLAUDE.md`의 "## 시작 흐름 (Startup)" 섹션, "새 소설 시작하자" 항목 아래에 추가:

```markdown
- **"새 만화 시작하자" / "만화 스토리보드"** → 신규 작성(만화): 장르/키워드 질문 → 한글 프로젝트명은 `--name-file` 규칙 그대로 → `python nf.py init --title <디렉토리명> --name-file projects/.initname.txt --type comic` → Phase 1
  - 소설과 동일한 4-Phase 흐름. 산출물만 페이지/컷 스토리보드. 분량 기준은 `comic_pages_per_episode`(기본 18p).
  - Phase 1 컨텍스트 생성 시 `tone.md`에 **"작화·연출 방향"** 섹션을 포함한다: 화풍 톤(극화체/명랑체 등), 페이지당 평균 컷 수·컷 분할 밀도, 말풍선·SFX 표기 관례.
```

- [ ] **Step 2: CLAUDE.md Phase 3에 만화 집필 포맷 규칙 추가**

`CLAUDE.md`의 "### Phase 3: 집필" 섹션 끝(파이프라인 모드 설명 다음, "*switch-auto*" 앞)에 추가:

```markdown
*만화 모드 (work_type=comic)*: 산출물은 산문이 아니라 출판만화형 스토리보드.
- 페이지=`## P{n}`, 컷=`### Cut {n}`. 각 컷 5필드 고정: **구도/카메라·연출·나레이션·대사·SFX** (없으면 `—`).
- 대사는 `(화자) "내용"`. 분량 게이트는 글자 수 대신 페이지 수(`char-count`가 `N/18페이지 (총 M컷)` 표시).
- 상세 포맷은 `nf/prompts/phase3_writing_comic.md` 참조. auto/scene/episode 3모드 동일하게 적용.
```

- [ ] **Step 3: CLAUDE.md 창작 규칙에 만화 포맷 추가**

`CLAUDE.md`의 "## 창작 규칙" 섹션에 "### 만화 스토리보드 포맷" 하위 절을 "### 전개 옵션 포맷" 앞에 추가:

```markdown
### 만화 스토리보드 포맷 (work_type=comic)

\`\`\`
## P{n}          ← 페이지
### Cut {n}      ← 컷
- **구도/카메라**: ...
- **연출**: ...
- **나레이션**: ...
- **대사**: (화자) "내용"
- **SFX**: ...
\`\`\`

- 필드 없으면 `—`. 페이지 배치 힌트는 `## P3 [3단 분할]`.
- 분량: `comic_pages_per_episode` 페이지(기본 18). `episodes/ep###.md`로 승격, 히스토리는 `ep###_making/`.
```

- [ ] **Step 4: CLAUDE.md CLI 레퍼런스에 init --type 반영**

`CLAUDE.md`의 CLI 명령 표에서 `init` 행을 교체:

```markdown
| `init <name> [--title <dir>] [--type novel\|comic]` | 새 프로젝트 생성 (comic=만화 스토리보드) |
```

그리고 `config` 행 설명에 `work_type`/`comic_pages_per_episode`를 키 예시에 추가:

```markdown
| `config <key> <value>` | 설정 (style_reference/writing_mode/auto_write/webnovel/work_type/comic_pages_per_episode) |
```

- [ ] **Step 5: README.md에 작품 유형 개념 + --type 반영**

`README.md`의 "## 워크플로우" 섹션 앞(또는 "시작하기"의 init 예시 부근)에 작품 유형 설명을 추가하고, CLI 표 `init` 행에 `--type` 반영:

```markdown
### 작품 유형 (v2.8)

`init --type {novel,comic}`로 작품 유형을 정한다. `comic`은 소설과 동일한 4-Phase 흐름을 타되 산출물이 **출판만화형 스토리보드**(페이지/컷 콘티)다. 분량 기준은 글자 수 대신 페이지 수(`comic_pages_per_episode`, 기본 18p).

\`\`\`bash
python nf.py init "내 만화" --title my-comic --type comic
\`\`\`

스토리보드 포맷: 페이지 `## P{n}`, 컷 `### Cut {n}`, 각 컷 5필드(구도/카메라·연출·나레이션·대사·SFX).
```

README CLI 기본 명령 표의 `init` 행을 교체:

```markdown
| `init <name> [--title <dir>] [--type novel\|comic]` | — | 새 프로젝트 생성 (comic=만화 스토리보드) |
```

- [ ] **Step 6: AGENTS.md에 work_type 분기 안내 추가**

`AGENTS.md`의 "### 새 CLI 명령을 추가할 때" 절 다음에 추가:

```markdown
### work_type 분기 (소설/만화)

`ProjectState.work_type`("novel"|"comic")이 산출물 종류를 가른다. 분량 집계/표시/게이트, 집필 프롬프트, `tone.md` 시드 3축에서만 분기하고 상태머신·전이는 공유한다. 분량 분기는 `work_type=="comic"`을 먼저 확인하고, 아니면 기존 `webnovel` 글자 로직으로 폴백한다. 페이지/컷 집계는 `ProjectFiles.count_pages` / `count_cuts`를 쓴다.
```

- [ ] **Step 7: 문서 일관성 확인**

Run: `python -c "import nf.cli, nf.state, nf.models, nf.fileops, nf.display, nf.interactive; print('OK')"`
Expected: `OK` (전체 모듈 import 무결성 최종 확인)

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md README.md AGENTS.md
git commit -m "docs(comic): 만화 스토리보드 모드 문서 동기화 (v2.8)"
```

---

## 최종 검증 (전체 e2e)

- [ ] **Step 1: 만화 프로젝트 전체 흐름 스모크**

```bash
python nf.py init comic_smoke --type comic
python nf.py status --project comic_smoke
python -c "open('projects/comic_smoke/drafts/sc001.md','w',encoding='utf-8').write('# ep\n'+''.join(f'## P{i}\n### Cut 1\n### Cut 2\n' for i in range(1,19)))"
python nf.py char-count drafts/sc001.md --project comic_smoke
```
Expected: init 만화 안내 → status 정상 → `18/18페이지 (총 36컷, 기준 충족)`

- [ ] **Step 2: 기존 소설 프로젝트 회귀 확인**

```bash
python nf.py status --project beyond-regression
```
Expected: 기존과 동일하게 동작 (work_type 미존재 → novel로 로드, 표시 변화 없음)

- [ ] **Step 3: 정리**

Run: `python -c "import shutil; shutil.rmtree('projects/comic_smoke')"`

---

## 스펙 대비 커버리지

| 스펙 항목 | 구현 태스크 |
|-----------|-------------|
| §2.1 work_type 필드 | Task 1 |
| §2.2 comic_pages_per_episode | Task 1, 2 |
| §3 init --type + 시작 흐름 | Task 3, 7 |
| §4.1 분량 집계/표시/게이트 | Task 4, 5 |
| §4.2 집필 프롬프트 | Task 6 (standalone 자동 분기는 후속) |
| §4.3 tone.md 작화 섹션 | Task 6 프롬프트 + Task 7 CLAUDE.md 지시 (passthrough 시 Claude Code가 tone.md에 반영) |
| §5 스토리보드 포맷 | Task 6, 7 |
| §6 CLI·문서 | Task 3, 7 |
| §7 하위 호환 | Task 1 Step 5, 최종 검증 Step 2 |
| §8 수동 검증 | 각 태스크 검증 단계 |
