"""출력 포맷팅: 한국어 레이블, 상태/항목 표시."""

from __future__ import annotations

from .models import Phase, Step, ItemStatus, ProjectState, Item

PHASE_LABELS = {
    Phase.PHASE1.value: "P1:컨텍스트",
    Phase.PHASE2.value: "P2:전개선정",
    Phase.PHASE3.value: "P3:집필",
    Phase.PHASE4.value: "P4:퇴고",
}

STEP_LABELS = {
    # Phase 1
    Step.DIRECTION_PROPOSAL.value: "방향성 제안",
    Step.DIRECTION_DECISION.value: "방향성 선정",
    Step.PLAN_BUILDUP.value: "기획안 빌드업",
    Step.PLAN_DECISION.value: "기획안 검토",
    Step.CONTEXT_CREATION.value: "컨텍스트 생성",
    # Phase 1 - v1.5 import
    Step.IMPORT_ANALYSIS.value: "원고 분석",
    Step.IMPORT_REVIEW.value: "임포트 검토",
    # Phase 2
    Step.DEVELOPMENT_PROPOSAL.value: "전개 옵션 생성",
    Step.DEVELOPMENT_DECISION.value: "전개 선정",
    Step.DEVELOPMENT_CONFIRM.value: "전개 확인",
    # Phase 3
    Step.STYLE_SETUP.value: "문체 설정",
    Step.MODE_SELECTION.value: "모드 선택",
    Step.WRITING.value: "집필",
    Step.SCENE_DECISION.value: "장면 검토",
    Step.WRITING_DECISION.value: "원고 검토",
    # Phase 4
    Step.PROOFREADING.value: "퇴고",
    Step.PROOFREAD_DECISION.value: "퇴고 검토",
    Step.CONTEXT_UPDATE.value: "컨텍스트 갱신",
    Step.CONTEXT_SIZE_CHECK.value: "크기 점검",
    Step.COMPLETE.value: "완료",
}

STATUS_MARKERS = {
    ItemStatus.PROPOSED.value: "[ ]",
    ItemStatus.SELECTED.value: "[*]",
    ItemStatus.HELD.value: "[~]",
    ItemStatus.DISCARDED.value: "[x]",
}


def ok(msg: str) -> str:
    return f"[OK] {msg}"


def error(msg: str) -> str:
    return f"[ERR] {msg}"


def step_msg(msg: str) -> str:
    return f"[STEP] {msg}"


def transition(msg: str) -> str:
    return f"→ {msg}"


def format_status(state: ProjectState) -> str:
    """현재 상태를 간결하게 포맷팅."""
    phase_label = PHASE_LABELS.get(state.phase, state.phase)
    step_label = STEP_LABELS.get(state.step, state.step)

    # 한 줄 핵심 상태
    line = f"{phase_label} > {step_label} | ep:{state.episode_count}"

    # 조건부 추가 정보 (있을 때만, 한 줄로)
    extras = []
    if state.revision_mode:
        extras.append(f"수정:{state.revision_episode}")
    if state.scene_count > 0:
        extras.append(f"장면:{state.scene_count}")
    if state.import_file:
        extras.append(f"임포트:{state.import_file}")
    if state.config.get("style_reference"):
        extras.append(f"문체:{state.config['style_reference']}")
    writing_mode = state.config.get("writing_mode")
    auto_write = state.config.get("auto_write", False)
    if auto_write:
        extras.append("auto")
    elif writing_mode:
        extras.append(f"mode:{writing_mode}")
    if state.revision_feedback:
        extras.append(f"피드백:\"{state.revision_feedback}\"")
    if state.draft_files:
        extras.append(f"drafts:[{','.join(state.draft_files)}]")

    if extras:
        line += " | " + " | ".join(extras)

    # 가능한 명령 (간결하게)
    from .state import get_valid_actions
    actions = get_valid_actions(state)
    if actions:
        line += f"\ncmd: {','.join(actions)}"

    return line


def format_items(state: ProjectState) -> str:
    """항목 목록: 활성 항목만 표시 (폐기 항목 제외)."""
    if not state.items:
        return "(항목 없음)"

    lines = []
    for item in state.items:
        # 폐기된 항목은 표시하지 않음
        if item.status == ItemStatus.DISCARDED.value:
            continue
        marker = STATUS_MARKERS.get(item.status, "[ ]")
        prob_str = f" p:{item.probability:.2f}" if item.probability is not None else ""
        lines.append(f"  {marker} {item.id}. {item.text}{prob_str}")

    if not lines:
        return "(활성 항목 없음)"

    if state.phase == Phase.PHASE2.value:
        lines.append(f"  선정:{state.selected_count()}/1")

    return "\n".join(lines)

def format_item_short(item: Item) -> str:
    """단일 항목을 짧게 포맷팅."""
    prob_str = f" p:{item.probability:.2f}" if item.probability is not None else ""
    return f"{item.id}. {item.text}{prob_str}"


def format_scenes(pf, state: ProjectState) -> str:
    """승인된 장면 목록과 글자 수 표시."""
    from .fileops import ProjectFiles
    from pathlib import Path

    scene_files = [df for df in state.draft_files if Path(df).name.startswith("sc")]
    if not scene_files:
        return "(장면 없음)"

    lines = []
    total_chars = 0
    for i, sf in enumerate(scene_files, 1):
        path = pf.root / sf
        if path.exists():
            text = path.read_text(encoding="utf-8")
            char_count = ProjectFiles.count_story_chars(text)
            total_chars += char_count
            lines.append(f"  {i}. {Path(sf).name} ({char_count:,}자)")
        else:
            lines.append(f"  {i}. {Path(sf).name} (없음)")

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
