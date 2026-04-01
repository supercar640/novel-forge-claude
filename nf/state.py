"""상태 머신: 전이 테이블, 유효성 검증, 실행 로직."""

from __future__ import annotations

from .models import Phase, Step, ItemStatus, ProjectState


# (phase, step) → 허용 명령어 목록
VALID_ACTIONS: dict[tuple[str, str], list[str]] = {
    # Phase 1
    (Phase.PHASE1.value, Step.DIRECTION_PROPOSAL.value): ["add", "next", "import-manuscript", "import-context"],
    (Phase.PHASE1.value, Step.DIRECTION_DECISION.value): ["items", "select", "hold", "discard", "retry"],
    (Phase.PHASE1.value, Step.PLAN_BUILDUP.value): ["save", "next"],
    (Phase.PHASE1.value, Step.PLAN_DECISION.value): ["approve", "revise", "reject"],
    (Phase.PHASE1.value, Step.CONTEXT_CREATION.value): ["next"],
    # Phase 1 - v1.5 import
    (Phase.PHASE1.value, Step.IMPORT_ANALYSIS.value): ["save", "next"],
    (Phase.PHASE1.value, Step.IMPORT_REVIEW.value): ["approve", "revise", "reject"],
    # Phase 2
    (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value): ["add", "next", "revise-episode"],
    (Phase.PHASE2.value, Step.DEVELOPMENT_DECISION.value): ["items", "select", "hold", "discard", "retry", "confirm-end"],
    (Phase.PHASE2.value, Step.DEVELOPMENT_CONFIRM.value): ["approve", "reject"],
    # Phase 3
    (Phase.PHASE3.value, Step.STYLE_SETUP.value): ["config", "next"],
    (Phase.PHASE3.value, Step.MODE_SELECTION.value): ["config", "next", "switch-auto"],
    (Phase.PHASE3.value, Step.WRITING.value): ["save", "next", "switch-auto"],
    (Phase.PHASE3.value, Step.SCENE_DECISION.value): ["approve", "revise", "reject", "merge-episode", "scenes"],
    (Phase.PHASE3.value, Step.WRITING_DECISION.value): ["approve", "revise", "reject", "hold", "pd-proofread"],
    # Phase 4
    (Phase.PHASE4.value, Step.PROOFREADING.value): ["save", "next", "pd-proofread"],
    (Phase.PHASE4.value, Step.PROOFREAD_DECISION.value): ["approve", "revise", "reject"],
    (Phase.PHASE4.value, Step.CONTEXT_UPDATE.value): ["context-update", "next"],
    (Phase.PHASE4.value, Step.CONTEXT_SIZE_CHECK.value): ["context-backup", "next"],
    (Phase.PHASE4.value, Step.COMPLETE.value): ["next", "revise-episode"],
}

# (phase, step, action) → (next_phase, next_step) 또는 callable
TRANSITIONS: dict[tuple[str, str, str], tuple[str, str]] = {
    # Phase 1
    (Phase.PHASE1.value, Step.DIRECTION_PROPOSAL.value, "next"): (Phase.PHASE1.value, Step.DIRECTION_DECISION.value),
    (Phase.PHASE1.value, Step.DIRECTION_DECISION.value, "select"): (Phase.PHASE1.value, Step.PLAN_BUILDUP.value),
    (Phase.PHASE1.value, Step.DIRECTION_DECISION.value, "retry"): (Phase.PHASE1.value, Step.DIRECTION_PROPOSAL.value),
    (Phase.PHASE1.value, Step.PLAN_BUILDUP.value, "next"): (Phase.PHASE1.value, Step.PLAN_DECISION.value),
    (Phase.PHASE1.value, Step.PLAN_DECISION.value, "approve"): (Phase.PHASE1.value, Step.CONTEXT_CREATION.value),
    (Phase.PHASE1.value, Step.PLAN_DECISION.value, "revise"): (Phase.PHASE1.value, Step.PLAN_BUILDUP.value),
    (Phase.PHASE1.value, Step.PLAN_DECISION.value, "reject"): (Phase.PHASE1.value, Step.DIRECTION_PROPOSAL.value),
    (Phase.PHASE1.value, Step.CONTEXT_CREATION.value, "next"): (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value),
    # Phase 1 - v1.5 import
    (Phase.PHASE1.value, Step.DIRECTION_PROPOSAL.value, "import-manuscript"): (Phase.PHASE1.value, Step.IMPORT_ANALYSIS.value),
    (Phase.PHASE1.value, Step.DIRECTION_PROPOSAL.value, "import-context"): (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value),
    (Phase.PHASE1.value, Step.IMPORT_ANALYSIS.value, "next"): (Phase.PHASE1.value, Step.IMPORT_REVIEW.value),
    (Phase.PHASE1.value, Step.IMPORT_REVIEW.value, "approve"): (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value),
    (Phase.PHASE1.value, Step.IMPORT_REVIEW.value, "revise"): (Phase.PHASE1.value, Step.IMPORT_ANALYSIS.value),
    (Phase.PHASE1.value, Step.IMPORT_REVIEW.value, "reject"): (Phase.PHASE1.value, Step.DIRECTION_PROPOSAL.value),
    # Phase 2
    (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value, "next"): (Phase.PHASE2.value, Step.DEVELOPMENT_DECISION.value),
    (Phase.PHASE2.value, Step.DEVELOPMENT_DECISION.value, "retry"): (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value),
    (Phase.PHASE2.value, Step.DEVELOPMENT_DECISION.value, "select"): (Phase.PHASE2.value, Step.DEVELOPMENT_CONFIRM.value),
    (Phase.PHASE2.value, Step.DEVELOPMENT_DECISION.value, "confirm-end"): (Phase.PHASE2.value, Step.DEVELOPMENT_CONFIRM.value),
    (Phase.PHASE2.value, Step.DEVELOPMENT_CONFIRM.value, "approve"): (Phase.PHASE3.value, Step.STYLE_SETUP.value),
    (Phase.PHASE2.value, Step.DEVELOPMENT_CONFIRM.value, "reject"): (Phase.PHASE2.value, Step.DEVELOPMENT_DECISION.value),
    # Phase 3
    (Phase.PHASE3.value, Step.STYLE_SETUP.value, "next"): (Phase.PHASE3.value, Step.MODE_SELECTION.value),
    (Phase.PHASE3.value, Step.MODE_SELECTION.value, "next"): (Phase.PHASE3.value, Step.WRITING.value),
    (Phase.PHASE3.value, Step.WRITING.value, "next"): (Phase.PHASE3.value, Step.WRITING_DECISION.value),
    # Scene mode transitions
    (Phase.PHASE3.value, Step.SCENE_DECISION.value, "approve"): (Phase.PHASE3.value, Step.WRITING.value),
    (Phase.PHASE3.value, Step.SCENE_DECISION.value, "revise"): (Phase.PHASE3.value, Step.WRITING.value),
    (Phase.PHASE3.value, Step.SCENE_DECISION.value, "reject"): (Phase.PHASE3.value, Step.WRITING.value),
    (Phase.PHASE3.value, Step.SCENE_DECISION.value, "merge-episode"): (Phase.PHASE3.value, Step.WRITING_DECISION.value),
    (Phase.PHASE3.value, Step.WRITING_DECISION.value, "approve"): (Phase.PHASE4.value, Step.PROOFREADING.value),
    (Phase.PHASE3.value, Step.WRITING_DECISION.value, "hold"): (Phase.PHASE3.value, Step.WRITING.value),
    (Phase.PHASE3.value, Step.WRITING_DECISION.value, "revise"): (Phase.PHASE3.value, Step.WRITING.value),
    (Phase.PHASE3.value, Step.WRITING_DECISION.value, "reject"): (Phase.PHASE3.value, Step.WRITING.value),
    # Phase 3 - v1.5 pd-proofread (PD가 직접 퇴고 → 컨텍스트 갱신으로 직행)
    (Phase.PHASE3.value, Step.WRITING_DECISION.value, "pd-proofread"): (Phase.PHASE4.value, Step.CONTEXT_UPDATE.value),
    # Phase 4
    (Phase.PHASE4.value, Step.PROOFREADING.value, "next"): (Phase.PHASE4.value, Step.PROOFREAD_DECISION.value),
    (Phase.PHASE4.value, Step.PROOFREAD_DECISION.value, "approve"): (Phase.PHASE4.value, Step.CONTEXT_UPDATE.value),
    (Phase.PHASE4.value, Step.PROOFREAD_DECISION.value, "revise"): (Phase.PHASE4.value, Step.PROOFREADING.value),
    (Phase.PHASE4.value, Step.PROOFREAD_DECISION.value, "reject"): (Phase.PHASE3.value, Step.WRITING.value),
    (Phase.PHASE4.value, Step.CONTEXT_UPDATE.value, "next"): (Phase.PHASE4.value, Step.CONTEXT_SIZE_CHECK.value),
    (Phase.PHASE4.value, Step.CONTEXT_SIZE_CHECK.value, "next"): (Phase.PHASE4.value, Step.COMPLETE.value),
    (Phase.PHASE4.value, Step.COMPLETE.value, "next"): (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value),
    # Phase 4 - v1.5 pd-proofread (퇴고 단계에서 PD 직접 퇴고 → 컨텍스트 갱신으로 직행)
    (Phase.PHASE4.value, Step.PROOFREADING.value, "pd-proofread"): (Phase.PHASE4.value, Step.CONTEXT_UPDATE.value),
    # v1.7: revise-episode (과거 회차 재수정)
    (Phase.PHASE2.value, Step.DEVELOPMENT_PROPOSAL.value, "revise-episode"): (Phase.PHASE3.value, Step.WRITING_DECISION.value),
    (Phase.PHASE4.value, Step.COMPLETE.value, "revise-episode"): (Phase.PHASE3.value, Step.WRITING_DECISION.value),
}


def get_valid_actions(state: ProjectState) -> list[str]:
    """현재 상태에서 유효한 명령어 목록 반환."""
    key = (state.phase, state.step)
    # status와 items는 항상 허용
    base = VALID_ACTIONS.get(key, [])
    return list(base)


def validate_action(state: ProjectState, action: str, **kwargs) -> str | None:
    """명령어 유효성 검증. 에러 메시지 반환, 유효하면 None."""
    valid = get_valid_actions(state)
    if action not in valid:
        return f"현재 단계({state.step})에서 '{action}' 명령을 사용할 수 없습니다. 가능한 명령: {', '.join(valid)}"

    if action == "select":
        item_ids = kwargs.get("item_ids", [])
        if not item_ids:
            return "선택할 항목 ID를 지정하세요."

        for item_id in item_ids:
            item = state.get_item(item_id)
            if item is None:
                return f"항목 {item_id}을(를) 찾을 수 없습니다."
            if item.status == ItemStatus.SELECTED.value:
                return f"항목 {item_id}은(는) 이미 선정되었습니다."
            if item.status == ItemStatus.DISCARDED.value:
                return f"항목 {item_id}은(는) 폐기된 항목입니다."

        if len(item_ids) != 1:
            return "정확히 1개만 선택할 수 있습니다."
        if state.phase == Phase.PHASE2.value:
            if state.selected_count() > 0:
                return "이미 1개를 선정했습니다."

    if action == "confirm-end":
        if state.selected_count() < 1:
            return "최소 1개 이상 선정해야 전개 선정을 종료할 수 있습니다."

    if action == "hold":
        # v1.7: writing_decision hold는 item_id 불요
        if state.step == Step.WRITING_DECISION.value:
            if not state.draft_files:
                return "보류할 초안 파일이 없습니다."
            return None
        item_id = kwargs.get("item_id")
        if item_id is not None:
            item = state.get_item(item_id)
            if item is None:
                return f"항목 {item_id}을(를) 찾을 수 없습니다."

    if action == "discard":
        item_id = kwargs.get("item_id")
        if item_id is not None:
            item = state.get_item(item_id)
            if item is None:
                return f"항목 {item_id}을(를) 찾을 수 없습니다."

    if action == "import-manuscript":
        filepath = kwargs.get("filepath", "")
        if not filepath:
            return "임포트할 원고 파일 경로를 지정하세요."

    if action == "revise-episode":
        filepath = kwargs.get("filepath", "")
        if not filepath:
            return "수정할 에피소드 파일을 지정하세요."

    if action == "pd-proofread":
        filepath = kwargs.get("filepath", "")
        if not filepath:
            return "퇴고된 원고 파일 경로를 지정하세요."

    if action == "merge-episode":
        if not state.draft_files:
            return "병합할 장면 파일이 없습니다."

    if action == "next":
        # Phase 1 direction_proposal: 항목이 있어야 진행
        if state.phase == Phase.PHASE1.value and state.step == Step.DIRECTION_PROPOSAL.value:
            if not state.items:
                return "방향성 항목을 추가한 후 진행하세요."
        # Phase 2 development_proposal: 항목이 있어야 진행
        if state.phase == Phase.PHASE2.value and state.step == Step.DEVELOPMENT_PROPOSAL.value:
            if not state.items:
                return "전개 옵션을 추가한 후 진행하세요."
        # mode_selection: writing_mode 또는 auto_write가 설정되어야 진행
        if state.step == Step.MODE_SELECTION.value:
            writing_mode = state.config.get("writing_mode")
            auto_write = state.config.get("auto_write", False)
            if not writing_mode and not auto_write:
                return "작성 모드를 설정해 주세요. (config writing_mode scene|episode / config auto_write true)"
        # writing/proofreading: draft_files 필요
        if state.step in (Step.WRITING.value, Step.PROOFREADING.value):
            if not state.draft_files:
                return "초안 파일을 저장(save)한 후 진행하세요."
        # v1.5: import_analysis: draft_files 필요
        if state.step == Step.IMPORT_ANALYSIS.value:
            if not state.draft_files:
                return "분석 결과를 저장(save)한 후 진행하세요."

    return None


def execute_action(state: ProjectState, action: str, **kwargs) -> tuple[ProjectState, str]:
    """명령 실행 후 (새 상태, 결과 메시지) 반환."""
    from . import display

    if action == "add":
        text = kwargs.get("text", "")
        probability = kwargs.get("probability")
        item_id = state.next_item_id()
        item = __import__("nf.models", fromlist=["Item"]).Item(
            id=item_id, text=text, probability=probability
        )
        state.items.append(item)
        return state, display.ok(f"항목 {item_id} 추가됨: {display.format_item_short(item)}")

    if action == "select":
        item_ids = kwargs.get("item_ids", [])
        selected_texts = []
        for item_id in item_ids:
            item = state.get_item(item_id)
            item.status = ItemStatus.SELECTED.value
            selected_texts.append(display.format_item_short(item))

        # Phase 1 & Phase 2: select triggers transition
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "select")]
        state.phase = next_phase
        state.step = next_step

        # Phase 2: 선정된 전개를 selected_developments에 저장
        if state.phase == Phase.PHASE2.value:
            selected = [item.text for item in state.items if item.status == ItemStatus.SELECTED.value]
            state.selected_developments = selected

        msg = display.ok(f"선정: {', '.join(selected_texts)}") + " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    if action == "hold":
        # v1.7: writing_decision hold → shelve로 보류 후 재작성
        if state.step == Step.WRITING_DECISION.value:
            shelve_file = kwargs.get("shelve_file", "")
            next_phase, next_step = TRANSITIONS[(state.phase, state.step, "hold")]
            state.phase = next_phase
            state.step = next_step
            state.draft_files = []
            state.scene_count = 0
            msg = display.ok(f"초안 보류: {shelve_file}") + " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
            return state, msg
        item_id = kwargs.get("item_id")
        item = state.get_item(item_id)
        item.status = ItemStatus.HELD.value
        return state, display.ok(f"보류: {display.format_item_short(item)}")

    if action == "discard":
        item_id = kwargs.get("item_id")
        item = state.get_item(item_id)
        item.status = ItemStatus.DISCARDED.value
        return state, display.ok(f"폐기: {display.format_item_short(item)}")

    if action == "retry":
        state.items = []
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "retry")]
        state.phase = next_phase
        state.step = next_step
        return state, display.ok("전체 폐기 후 재생성 대기. 새로운 항목을 추가(add)하세요.")

    if action == "approve":
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "approve")]
        old_step = state.step
        state.phase = next_phase
        state.step = next_step
        state.revision_feedback = None
        # v1.5: import_review 승인 시 정리
        # v1.7: episode_count 증가 (임포트 원고 = ep001), import_file은 cli/interactive에서 정리
        if old_step == Step.IMPORT_REVIEW.value:
            state.episode_count += 1
            state.items = []
            state.draft_files = []
        # Scene mode: scene_decision approve → scene_count++, draft_files 유지
        if old_step == Step.SCENE_DECISION.value:
            state.scene_count += 1
            msg = display.ok(f"장면 {state.scene_count} 승인") + " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
            return state, msg
        msg = display.ok("승인 완료")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    if action == "revise":
        feedback = kwargs.get("feedback", "")
        state.revision_feedback = feedback
        old_step = state.step
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "revise")]
        state.phase = next_phase
        state.step = next_step
        # Scene mode: scene_decision revise → 마지막 장면만 제거 (나머지 유지)
        if old_step == Step.SCENE_DECISION.value:
            if state.draft_files:
                state.draft_files.pop()
        # WRITING_DECISION revise → scene_count 리셋
        elif old_step == Step.WRITING_DECISION.value:
            state.scene_count = 0
            state.draft_files = []
        else:
            state.draft_files = []
        msg = display.ok(f"수정 요청: {feedback}")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    if action == "reject":
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "reject")]
        old_step = state.step
        state.phase = next_phase
        state.step = next_step
        state.revision_feedback = None
        # Scene mode: scene_decision reject → 마지막 장면만 제거
        if old_step == Step.SCENE_DECISION.value:
            if state.draft_files:
                state.draft_files.pop()
        # WRITING_DECISION reject → scene_count 리셋
        elif old_step == Step.WRITING_DECISION.value:
            state.scene_count = 0
            state.draft_files = []
        else:
            state.draft_files = []
        # v1.5: import_review 거부 시 import_file 정리
        if old_step == Step.IMPORT_REVIEW.value:
            state.import_file = None
        msg = display.ok("폐기됨")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    if action == "confirm-end":
        # 선정된 항목을 selected_developments에 저장
        selected = [item.text for item in state.items if item.status == ItemStatus.SELECTED.value]
        state.selected_developments = selected
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "confirm-end")]
        state.phase = next_phase
        state.step = next_step
        msg = display.ok(f"전개 {len(selected)}개 선정. approve/reject?")
        return state, msg

    if action == "save":
        filepath = kwargs.get("filepath", "")
        save_type = kwargs.get("save_type", "manuscript")
        # proofread 저장 시 기존 non-auto draft 파일을 교체 (퇴고본이 최종본)
        if save_type == "proofread":
            from pathlib import Path as _P
            state.draft_files = [
                df for df in state.draft_files
                if _P(df).name.startswith("auto_")
            ]
        if filepath not in state.draft_files:
            state.draft_files.append(filepath)
        return state, display.ok(f"초안 저장됨: {filepath}")

    if action == "config":
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")
        if key == "writing_mode":
            if value not in ("scene", "episode"):
                return state, display.error("writing_mode는 'scene' 또는 'episode'만 가능합니다.")
            state.config["writing_mode"] = value
            # v1.7: 상호 배타 — writing_mode 설정 시 auto_write 해제
            state.config["auto_write"] = False
            return state, display.ok(f"설정 변경: 작성모드 = {value}")
        if key == "auto_write":
            if value.lower() not in ("true", "false"):
                return state, display.error("auto_write는 'true' 또는 'false'만 가능합니다.")
            state.config["auto_write"] = value.lower() == "true"
            # v1.7: 상호 배타 — auto_write 설정 시 writing_mode 해제
            if state.config["auto_write"]:
                state.config["writing_mode"] = None
            return state, display.ok(f"설정 변경: 자동작성 = {state.config['auto_write']}")
        # v2.0: mode (standalone/passthrough) — ai_config.json에 저장
        if key == "mode":
            if value not in ("standalone", "passthrough"):
                return state, display.error("mode는 'standalone' 또는 'passthrough'만 가능합니다.")
            # mode는 state.json이 아닌 ai_config.json에 저장
            return state, display.ok(f"설정 변경: mode = {value} (ai_config.json에 저장하려면 ai-provider 명령 사용)")
        if key not in ("style_reference",):
            return state, display.error(f"알 수 없는 설정 키: {key}. 사용 가능: style_reference, writing_mode, auto_write, mode")
        state.config[key] = value
        return state, display.ok(f"설정 변경: {key} = {value}")

    if action == "context-update":
        return state, display.ok("컨텍스트 갱신 완료 표시됨. 'next'로 진행하세요.")

    if action == "context-backup":
        # 실제 백업은 fileops에서 처리, 여기서는 상태만 업데이트
        state.context_version += 1
        return state, display.ok(f"컨텍스트 백업 준비 (v{state.context_version}). 'next'로 진행하세요.")

    # v1.5: import-manuscript
    if action == "import-manuscript":
        filepath = kwargs.get("filepath", "")
        state.import_file = filepath
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "import-manuscript")]
        state.phase = next_phase
        state.step = next_step
        state.items = []
        msg = display.ok(f"원고 임포트: {filepath}")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    # v1.5: import-context
    if action == "import-context":
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "import-context")]
        state.phase = next_phase
        state.step = next_step
        state.items = []
        state.draft_files = []
        state.import_file = None
        msg = display.ok("기존 컨텍스트 임포트 완료")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    # v1.5: pd-proofread
    if action == "pd-proofread":
        filepath = kwargs.get("filepath", "")
        # 기존 non-auto draft 제거 (save proofread와 동일 정리)
        from pathlib import Path as _P
        state.draft_files = [
            df for df in state.draft_files
            if _P(df).name.startswith("auto_")
        ]
        if filepath not in state.draft_files:
            state.draft_files.append(filepath)
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "pd-proofread")]
        state.phase = next_phase
        state.step = next_step
        msg = display.ok(f"PD 퇴고 원고 등록: {filepath}")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    # v1.7: revise-episode (과거 회차 재수정)
    if action == "revise-episode":
        filepath = kwargs.get("filepath", "")
        original_episode = kwargs.get("original_episode", "")
        state.revision_mode = True
        state.revision_episode = original_episode
        state.revision_return_phase = state.phase
        state.revision_return_step = state.step
        state.draft_files = [filepath]
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "revise-episode")]
        state.phase = next_phase
        state.step = next_step
        msg = display.ok(f"에피소드 수정 모드: {original_episode}")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    # v1.5: switch-auto
    if action == "switch-auto":
        state.config["auto_write"] = True
        state.config["writing_mode"] = None  # v1.7: 상호 배타
        return state, display.ok("자동작성(auto) 모드로 전환됨. AI가 3화 분량을 자율 연쓰기합니다.")

    # Scene mode: merge-episode (실제 파일 병합은 cli/interactive에서 처리)
    if action == "merge-episode":
        merged_file = kwargs.get("merged_file", "")
        state.draft_files = [merged_file]
        state.scene_count = 0
        next_phase, next_step = TRANSITIONS[(state.phase, state.step, "merge-episode")]
        state.phase = next_phase
        state.step = next_step
        msg = display.ok(f"장면 병합 완료: {merged_file}")
        msg += " " + display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    # Scene mode: scenes (상태 변경 없음, 표시만)
    if action == "scenes":
        return state, ""

    if action == "next":
        key = (state.phase, state.step, "next")
        if key not in TRANSITIONS:
            return state, display.error(f"현재 단계에서 'next' 전이가 정의되지 않았습니다.")

        next_phase, next_step = TRANSITIONS[key]

        # Scene mode: WRITING → SCENE_DECISION (episode mode이면 WRITING_DECISION 유지)
        if state.step == Step.WRITING.value and state.config.get("writing_mode") == "scene":
            next_step = Step.SCENE_DECISION.value

        # Phase 4 complete → Phase 2: 에피소드 카운트 증가, items 초기화
        if state.step == Step.COMPLETE.value:
            # v1.7: revision_mode일 때는 episode_count 증가하지 않고 원래 위치로 복귀
            if state.revision_mode:
                next_phase = state.revision_return_phase
                next_step = state.revision_return_step
                state.revision_mode = False
                state.revision_episode = None
                state.revision_return_phase = None
                state.revision_return_step = None
                state.scene_count = 0
                state.items = []
                state.draft_files = []
                state.revision_feedback = None
                state.config["writing_mode"] = None
                state.config["auto_write"] = False
            else:
                # PD/auto 트랙별 개수를 세서 최대값만큼 episode_count 증가
                from pathlib import Path as _Path
                pd_count = 0
                auto_count = 0
                for df in list(dict.fromkeys(state.draft_files)):
                    if _Path(df).name.startswith("auto_"):
                        auto_count += 1
                    else:
                        pd_count += 1
                state.episode_count += max(pd_count, auto_count, 1)
                state.scene_count = 0
                state.items = []
                state.selected_developments = []
                state.draft_files = []
                state.revision_feedback = None
                state.config["writing_mode"] = None
                state.config["auto_write"] = False

        # Phase 1 context_creation → Phase 2: items 초기화
        if state.step == Step.CONTEXT_CREATION.value:
            state.items = []
            state.draft_files = []

        # Phase 2 → Phase 3: items 초기화
        if state.step == Step.DEVELOPMENT_CONFIRM.value:
            pass  # selected_developments는 유지

        # retry로 돌아갈 때 items 초기화
        if state.step == Step.DIRECTION_DECISION.value or state.step == Step.DEVELOPMENT_DECISION.value:
            pass  # retry는 별도 처리

        # plan_decision reject → direction_proposal: items 초기화
        if state.step == Step.PLAN_DECISION.value and next_step == Step.DIRECTION_PROPOSAL.value:
            state.items = []

        # v1.5: import_review reject → direction_proposal: 정리
        if state.step == Step.IMPORT_REVIEW.value and next_step == Step.DIRECTION_PROPOSAL.value:
            state.items = []
            state.import_file = None

        state.phase = next_phase
        state.step = next_step

        msg = display.transition(display.STEP_LABELS.get(state.step, state.step))
        return state, msg

    return state, display.error(f"알 수 없는 명령: {action}")
