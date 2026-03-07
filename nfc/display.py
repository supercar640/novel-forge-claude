"""출력 포맷팅: 한국어 레이블, 상태/항목 표시."""

from __future__ import annotations

from .models import Phase, Step, ItemStatus, ProjectState, Item

PHASE_LABELS = {
    Phase.PHASE1.value: "Phase 1: 컨텍스트 수립",
    Phase.PHASE2.value: "Phase 2: 전개 선정",
    Phase.PHASE3.value: "Phase 3: 집필",
    Phase.PHASE4.value: "Phase 4: 퇴고 및 컨텍스트 갱신",
}

STEP_LABELS = {
    # Phase 1
    Step.DIRECTION_PROPOSAL.value: "방향성 제안",
    Step.DIRECTION_DECISION.value: "방향성 선정",
    Step.PLAN_BUILDUP.value: "기획안 빌드업",
    Step.PLAN_DECISION.value: "기획안 검토",
    Step.CONTEXT_CREATION.value: "컨텍스트 생성",
    # Phase 1 - v1.5 import
    Step.IMPORT_ANALYSIS.value: "원고 분석 및 컨텍스트 생성",
    Step.IMPORT_REVIEW.value: "임포트 컨텍스트 검토",
    # Phase 2
    Step.DEVELOPMENT_PROPOSAL.value: "전개 옵션 생성",
    Step.DEVELOPMENT_DECISION.value: "전개 선정",
    Step.DEVELOPMENT_CONFIRM.value: "전개 선정 확인",
    # Phase 3
    Step.STYLE_SETUP.value: "문체 설정",
    Step.MODE_SELECTION.value: "작성 모드 선택",
    Step.WRITING.value: "집필",
    Step.SCENE_DECISION.value: "장면 검토",
    Step.WRITING_DECISION.value: "원고 검토",
    # Phase 4
    Step.PROOFREADING.value: "퇴고",
    Step.PROOFREAD_DECISION.value: "퇴고 검토",
    Step.CONTEXT_UPDATE.value: "컨텍스트 갱신",
    Step.CONTEXT_SIZE_CHECK.value: "컨텍스트 크기 점검",
    Step.COMPLETE.value: "회차 완료",
}

STATUS_LABELS = {
    ItemStatus.PROPOSED.value: "제안됨",
    ItemStatus.SELECTED.value: "선정됨",
    ItemStatus.HELD.value: "보류",
    ItemStatus.DISCARDED.value: "폐기됨",
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
    return f"[ERROR] {msg}"


def step_msg(msg: str) -> str:
    return f"[STEP] {msg}"


def transition(msg: str) -> str:
    return f"[TRANSITION] {msg}"


def format_status(state: ProjectState) -> str:
    """현재 상태를 포맷팅하여 반환."""
    phase_label = PHASE_LABELS.get(state.phase, state.phase)
    step_label = STEP_LABELS.get(state.step, state.step)

    lines = [
        f"프로젝트: {state.project_name}",
        f"Phase:    {phase_label}",
        f"Step:     {step_label}",
        f"에피소드: {state.episode_count}화",
    ]

    if state.revision_mode:
        lines.append(f"수정모드: {state.revision_episode} 수정 중")
    if state.scene_count > 0:
        lines.append(f"장면:     {state.scene_count}개 완료")
    if state.import_file:
        lines.append(f"임포트:   {state.import_file}")
    if state.config.get("style_reference"):
        lines.append(f"문체:     {state.config['style_reference']}")
    writing_mode = state.config.get("writing_mode")
    auto_write = state.config.get("auto_write", False)
    if writing_mode or auto_write:
        def _mode_label(m: str) -> str:
            if m == "scene":
                return "장면별"
            elif m == "episode":
                return "1화 분량"
            return m or ""
        parts = []
        if auto_write:
            parts.append("자동작성(3화)")
        if writing_mode:
            parts.append(_mode_label(writing_mode))
        mode_str = " + ".join(parts)
        lines.append(f"작성모드: {mode_str}")
    if state.revision_feedback:
        lines.append(f"수정요청: {state.revision_feedback}")
    if state.draft_files:
        if len(state.draft_files) == 1:
            lines.append(f"초안파일: {state.draft_files[0]}")
        else:
            lines.append(f"초안파일: {', '.join(state.draft_files)}")

    from .state import get_valid_actions
    actions = get_valid_actions(state)
    if actions:
        lines.append(f"가능한 명령: {', '.join(actions)}")

    return "\n".join(lines)


def format_items(state: ProjectState) -> str:
    """항목 목록을 포맷팅하여 반환."""
    if not state.items:
        return "등록된 항목이 없습니다."

    lines = []
    for item in state.items:
        marker = STATUS_MARKERS.get(item.status, "[ ]")
        prob_str = f" (prob: {item.probability:.2f})" if item.probability is not None else ""
        status_label = STATUS_LABELS.get(item.status, item.status)
        lines.append(f"  {marker} {item.id}. {item.text}{prob_str} — {status_label}")

    selected = state.selected_count()
    if state.phase == Phase.PHASE2.value:
        lines.append(f"\n선정: {selected}/1")

    return "\n".join(lines)

def format_item_short(item: Item) -> str:
    """단일 항목을 짧게 포맷팅."""
    prob_str = f" (prob: {item.probability:.2f})" if item.probability is not None else ""
    return f"{item.id}. {item.text}{prob_str}"


def format_scenes(pf, state: ProjectState) -> str:
    """승인된 장면 목록과 글자 수 표시."""
    from .fileops import ProjectFiles
    from pathlib import Path

    scene_files = [df for df in state.draft_files if Path(df).name.startswith("sc")]
    if not scene_files:
        return "등록된 장면이 없습니다."

    lines = ["=== 장면 목록 ==="]
    total_chars = 0
    for i, sf in enumerate(scene_files, 1):
        path = pf.root / sf
        if path.exists():
            text = path.read_text(encoding="utf-8")
            char_count = ProjectFiles.count_story_chars(text)
            total_chars += char_count
            lines.append(f"  {i}. {Path(sf).name} ({char_count:,}자)")
        else:
            lines.append(f"  {i}. {Path(sf).name} (파일 없음)")

    lines.append("  " + "─" * 20)
    lines.append(f"  누적: {total_chars:,}자 / 5,500자 기준")
    return "\n".join(lines)
