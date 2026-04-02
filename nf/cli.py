# -*- coding: utf-8 -*-
"""argparse CLI routing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .models import ItemStatus, Phase, ProjectState, Step
from .fileops import ProjectFiles, find_project_root
from .state import validate_action, execute_action, get_valid_actions
from . import display


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nf",
        description="Novel Factory - CLI",
    )
    parser.add_argument("--project", "-P", default=None,
                        help="프로젝트 디렉토리명 지정")
    sub = parser.add_subparsers(dest="command", help="command")

    p_init = sub.add_parser("init", help="new project")
    p_init.add_argument("name", help="project name")
    p_init.add_argument("--title", help="english dir name", default=None)

    sub.add_parser("status", help="show status")
    sub.add_parser("items", help="list items")

    p_add = sub.add_parser("add", help="add item")
    p_add.add_argument("text", help="item text")
    p_add.add_argument("-p", "--probability", type=float, default=None, help="probability")

    p_select = sub.add_parser("select", help="select items")
    p_select.add_argument("ids", nargs="+", type=int, help="item IDs")

    p_hold = sub.add_parser("hold", help="hold item or draft")
    p_hold.add_argument("id", nargs="?", type=int, default=None, help="item ID (optional at writing_decision)")

    p_discard = sub.add_parser("discard", help="discard item")
    p_discard.add_argument("id", type=int, help="item ID")

    sub.add_parser("retry", help="retry all")
    sub.add_parser("approve", help="approve")

    p_revise = sub.add_parser("revise", help="revise")
    p_revise.add_argument("feedback", help="feedback")

    sub.add_parser("reject", help="reject")
    sub.add_parser("confirm-end", help="confirm end (Phase 2)")

    p_save = sub.add_parser("save", help="save draft")
    p_save.add_argument("type", choices=["plan", "manuscript", "proofread"], help="save type")
    p_save.add_argument("file", help="file path")

    p_config = sub.add_parser("config", help="config")
    p_config.add_argument("key", help="config key")
    p_config.add_argument("value", help="config value")

    sub.add_parser("context-update", help="context update done")
    sub.add_parser("context-backup", help="context backup")
    sub.add_parser("next", help="next step")
    sub.add_parser("merge-episode", help="merge scenes into episode")
    sub.add_parser("scenes", help="list scenes with char counts")

    p_char_count = sub.add_parser("char-count", help="count story characters in file")
    p_char_count.add_argument("file", help="file path to count")

    # v1.5: new commands
    p_import_ms = sub.add_parser("import-manuscript", help="import manuscript for analysis")
    p_import_ms.add_argument("file", help="manuscript file path")

    sub.add_parser("import-context", help="import existing context files")

    p_pd_proofread = sub.add_parser("pd-proofread", help="register PD proofread manuscript")
    p_pd_proofread.add_argument("file", help="proofread file path")

    sub.add_parser("switch-auto", help="switch to auto writing mode")

    # v1.7: revise-episode
    p_revise_ep = sub.add_parser("revise-episode", help="v1.7: revise a completed episode")
    p_revise_ep.add_argument("file", help="episode file name (e.g., ep001.md)")

    # v2.0: AI provider config
    p_ai = sub.add_parser("ai-config", help="v2.0: show AI provider config")
    p_ai_provider = sub.add_parser("ai-provider", help="v2.0: set AI provider for a phase")
    p_ai_provider.add_argument("provider_type", help="provider type (anthropic/openai/custom)")
    p_ai_provider.add_argument("--model", "-m", required=True, help="model name")
    p_ai_provider.add_argument("--phase", default="default",
                                help="phase to configure (default/phase1/phase2/phase3/phase4)")
    p_ai_provider.add_argument("--api-key-env", default=None, help="env var name for API key")
    p_ai_provider.add_argument("--base-url", default=None, help="custom API base URL")
    p_ai_provider.add_argument("--temperature", type=float, default=None, help="temperature")
    p_ai_provider.add_argument("--max-tokens", type=int, default=None, help="max tokens")

    p_ai_validate = sub.add_parser("ai-validate", help="v2.0: validate AI provider setup")

    sub.add_parser("ai-mode", help="v2.0: show/toggle standalone vs passthrough mode")
    sub.add_parser("ai-cost", help="v2.0: show token usage and cost summary")
    sub.add_parser("ai-cost-reset", help="v2.0: reset cost tracking log")

    return parser


def load_project(project_name=None):
    root = find_project_root(project_name=project_name)
    if root is None:
        msg = "project not found. use 'nf init <name>'"
        if project_name:
            msg = f"project '{project_name}' not found."
        print(display.error(msg))
        sys.exit(1)
    pf = ProjectFiles.load(root)
    state = pf.read_state()
    return pf, state


def run_action(pf, state, action, **kwargs):
    err = validate_action(state, action, **kwargs)
    if err:
        print(display.error(err))
        sys.exit(1)
    state, msg = execute_action(state, action, **kwargs)
    pf.save_state(state)
    print(msg)


MIN_STORY_CHARS = 5500


def check_draft_length(pf, state):
    """writing_decision 단계에서 approve 시 draft 분량 검증."""
    if state.step != Step.WRITING_DECISION.value:
        return None
    if not state.config.get("webnovel", True):
        return None
    if not state.draft_files:
        return None
    for df in state.draft_files:
        draft_path = pf.root / df
        if not draft_path.exists():
            continue
        text = draft_path.read_text(encoding="utf-8")
        char_count = ProjectFiles.count_story_chars(text)
        if char_count < MIN_STORY_CHARS:
            return (
                f"원고 분량 미달: {df} ({char_count:,}자 / 최소 {MIN_STORY_CHARS:,}자). "
                f"{MIN_STORY_CHARS - char_count:,}자 추가 필요."
            )
    return None


_SHORTCUT_MAP = {"s": "select", "h": "hold", "d": "discard"}


def _expand_shortcuts(argv):
    """'s1' → ['select', '1'], 'h2' → ['hold', '2'] 등 단축키+숫자 전처리."""
    import re
    if not argv:
        return argv
    m = re.match(r'^([shd])(\d+)$', argv[0], re.IGNORECASE)
    if m:
        cmd = _SHORTCUT_MAP[m.group(1).lower()]
        return [cmd, m.group(2)] + list(argv[1:])
    return argv


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = _expand_shortcuts(argv)
    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)

    # --project/-P가 서브커맨드 뒤에 온 경우 추출
    if remaining and not args.project:
        _sub = argparse.ArgumentParser(add_help=False)
        _sub.add_argument("--project", "-P", default=None)
        _sub_args, leftover = _sub.parse_known_args(remaining)
        if _sub_args.project:
            args.project = _sub_args.project
            remaining = leftover
    # 인식되지 않은 인자가 남아있으면 기존 파서로 에러 출력
    if remaining:
        parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        handle_init(args)
        return

    pf, state = load_project(project_name=args.project)

    if args.command == "status":
        print(display.format_status(state))
    elif args.command == "items":
        print(display.format_items(state))
    elif args.command == "add":
        run_action(pf, state, "add", text=args.text, probability=args.probability)
    elif args.command == "select":
        handle_select(pf, state, args.ids)
    elif args.command == "hold":
        handle_hold(pf, state, args.id)
    elif args.command == "discard":
        run_action(pf, state, "discard", item_id=args.id)
    elif args.command == "retry":
        run_action(pf, state, "retry")
    elif args.command == "approve":
        err = check_draft_length(pf, state)
        if err:
            print(display.error(err))
            sys.exit(1)
        # v1.7: import_review approve → 임포트 원고를 ep001로 저장
        was_import_review = (state.step == Step.IMPORT_REVIEW.value)
        import_file_path = state.import_file
        run_action(pf, state, "approve")
        if was_import_review and import_file_path:
            _save_imported_episode(pf, state, import_file_path)
    elif args.command == "revise":
        run_action(pf, state, "revise", feedback=args.feedback)
    elif args.command == "reject":
        run_action(pf, state, "reject")
    elif args.command == "confirm-end":
        run_action(pf, state, "confirm-end")
    elif args.command == "save":
        handle_save(pf, state, args)
    elif args.command == "config":
        run_action(pf, state, "config", key=args.key, value=args.value)
    elif args.command == "context-update":
        run_action(pf, state, "context-update")
    elif args.command == "context-backup":
        handle_context_backup(pf, state)
    elif args.command == "next":
        handle_next(pf, state)
    # v1.5: new commands
    elif args.command == "import-manuscript":
        handle_import_manuscript(pf, state, args)
    elif args.command == "import-context":
        handle_import_context(pf, state)
    elif args.command == "pd-proofread":
        handle_pd_proofread(pf, state, args)
    elif args.command == "switch-auto":
        run_action(pf, state, "switch-auto")
    elif args.command == "revise-episode":
        handle_revise_episode(pf, state, args)
    elif args.command == "merge-episode":
        handle_merge_episode(pf, state)
    elif args.command == "scenes":
        handle_scenes(pf, state)
    elif args.command == "char-count":
        handle_char_count(pf, state, args)
    # v2.0: AI provider config commands
    elif args.command == "ai-config":
        handle_ai_config(pf)
    elif args.command == "ai-provider":
        handle_ai_provider(pf, args)
    elif args.command == "ai-validate":
        handle_ai_validate(pf)
    elif args.command == "ai-mode":
        handle_ai_mode(pf)
    elif args.command == "ai-cost":
        handle_ai_cost(pf)
    elif args.command == "ai-cost-reset":
        handle_ai_cost_reset(pf)
    else:
        parser.print_help()


def handle_select(pf, state, item_ids):
    """select 처리 + 미선정 active 항목을 자동 shelve."""
    selected_set = set(item_ids)
    # 선정 전에 나머지 active 항목을 shelve
    if state.step in (Step.DIRECTION_DECISION.value, Step.DEVELOPMENT_DECISION.value):
        for item in state.items:
            if item.id not in selected_set and item.status == ItemStatus.PROPOSED.value:
                item.status = ItemStatus.HELD.value
                prefix = "idea" if state.phase == Phase.PHASE1.value else "dev"
                shelve_path = pf.save_to_shelve(item.text, item.id, prefix, item.probability)
                print(display.ok(f"자동 보류: {display.format_item_short(item)} → {shelve_path.name}"))
    run_action(pf, state, "select", item_ids=item_ids)


def handle_hold(pf, state, item_id):
    """v1.7: hold 처리 + shelve 저장."""
    # writing_decision hold → draft를 shelve로 보류
    if state.step == Step.WRITING_DECISION.value:
        _handle_writing_hold(pf, state)
        return
    # Phase 1/2 item hold + shelve 저장
    item = state.get_item(item_id)
    run_action(pf, state, "hold", item_id=item_id)
    if item and state.step in (Step.DIRECTION_DECISION.value, Step.DEVELOPMENT_DECISION.value):
        prefix = "idea" if state.phase == Phase.PHASE1.value else "dev"
        shelve_path = pf.save_to_shelve(item.text, item.id, prefix, item.probability)
        print(display.ok(f"shelve 디렉토리에 {shelve_path.name}로 저장하였습니다."))


def _handle_writing_hold(pf, state):
    """v1.7: writing_decision에서 hold → draft를 shelve/에 저장 후 재작성."""
    err = validate_action(state, "hold")
    if err:
        print(display.error(err))
        sys.exit(1)
    shelve_dir = pf.root / "shelve"
    shelve_dir.mkdir(exist_ok=True)
    shelve_names = []
    for df in state.draft_files:
        draft_path = pf.root / df
        if draft_path.exists():
            content = draft_path.read_text(encoding="utf-8")
            ep_num = state.episode_count + 1
            filename = f"draft_ep{ep_num:03d}_{Path(df).name}"
            target = shelve_dir / filename
            counter = 1
            while target.exists():
                filename = f"draft_ep{ep_num:03d}_{Path(df).stem}_{counter}.md"
                target = shelve_dir / filename
                counter += 1
            target.write_text(content, encoding="utf-8")
            shelve_names.append(filename)
    shelve_file_str = ", ".join(shelve_names) if shelve_names else "없음"
    state, msg = execute_action(state, "hold", shelve_file=shelve_file_str)
    pf.save_state(state)
    print(msg)
    for name in shelve_names:
        print(display.ok(f"shelve 디렉토리에 {name}로 저장하였습니다."))


def _save_imported_episode(pf, state, import_file_path):
    """v1.7: 임포트 원고를 episodes/ep001.md로 저장하고 import_file 정리."""
    source = pf.root / import_file_path
    if not source.exists():
        source = Path(import_file_path)
    if source.exists():
        content = source.read_text(encoding="utf-8")
        ep_path = pf.save_episode(1, content, prefix="ep")
        print(display.ok(f"임포트 원고 저장: {ep_path.name}"))
    state.import_file = None
    pf.save_state(state)


def handle_init(args):
    name = args.name
    title = args.title
    if title is None:
        import re
        title = re.sub(r"[^\w\s-]", "", name)
        title = re.sub(r"\s+", "_", title).strip("_").lower()
        if not title:
            title = "novel_project"
    base_dir = Path.cwd() / "projects"
    base_dir.mkdir(exist_ok=True)
    try:
        pf = ProjectFiles.create_project(base_dir, name, title)
        print(display.ok("project created: " + str(pf.root)))
        print(display.step_msg("Phase 1: direction proposal"))
        print("  use 'add' to add directions")
    except FileExistsError as e:
        print(display.error(str(e)))
        sys.exit(1)


def handle_next(pf, state):
    # context_update -> context_size_check: save episode(s) early for safety
    if state.step == Step.CONTEXT_UPDATE.value and state.draft_files:
        # v1.7: revision_mode일 때 에피소드 갱신
        if state.revision_mode and state.revision_episode:
            df = state.draft_files[-1]  # 최종본만 사용
            draft_path = pf.root / df
            ep_path = pf.episodes_dir / state.revision_episode
            is_original_copy = Path(df).name.startswith("revision_")
            if draft_path.exists() and ep_path.exists():
                draft_content = draft_path.read_text(encoding="utf-8")
                ep_content = ep_path.read_text(encoding="utf-8")
                if draft_content.strip() == ep_content.strip():
                    # 동일 → char count만 재주입
                    content = pf.inject_char_count(ep_content)
                    ep_path.write_text(content, encoding="utf-8")
                    print(display.ok(f"에피소드 확인 완료: {ep_path.name}"))
                elif is_original_copy:
                    # revision_ 파일(원본 복사본)이 episode와 다름
                    # → episode가 직접 수정된 것으로 간주, episode 내용 유지
                    content = pf.inject_char_count(ep_content)
                    ep_path.write_text(content, encoding="utf-8")
                    print(display.ok(f"에피소드 확인 완료 (직접 수정 반영): {ep_path.name}"))
                else:
                    # 퇴고 산출물(ep_proofread.md 등) → draft 내용으로 갱신
                    content = pf.inject_char_count(draft_content)
                    ep_path.write_text(content, encoding="utf-8")
                    print(display.ok(f"에피소드 수정 완료: {ep_path.name}"))
            elif draft_path.exists():
                content = draft_path.read_text(encoding="utf-8")
                content = pf.inject_char_count(content)
                ep_path.write_text(content, encoding="utf-8")
                print(display.ok(f"에피소드 수정 완료: {ep_path.name}"))
        else:
            pd_num = state.episode_count + 1
            auto_num = state.episode_count + 1
            for df in list(dict.fromkeys(state.draft_files)):
                draft_path = pf.root / df
                filename = Path(df).name
                is_auto = filename.startswith("auto_")
                if is_auto:
                    prefix = "auto_ep"
                    episode_num = auto_num
                    auto_num += 1
                else:
                    prefix = "ep"
                    episode_num = pd_num
                    pd_num += 1
                if draft_path.exists():
                    content = draft_path.read_text(encoding="utf-8")
                    ep_path = pf.save_episode(episode_num, content, prefix=prefix)
                    print(display.ok("episode saved: " + ep_path.name))
                else:
                    ep_name = f"{prefix}{episode_num:03d}.md"
                    print(display.ok("episode: episodes/" + ep_name + " (no draft file - manual save needed)"))
    run_action(pf, state, "next")


def handle_save(pf, state, args):
    filepath = args.file
    # proofread 저장 시: 기존 manuscript draft 내용을 proofread 파일로 복사
    # 단, 이미 존재하면 AI가 작성한 퇴고본으로 간주하여 복사 생략
    if args.type == "proofread" and state.draft_files:
        import shutil
        src_path = pf.root / state.draft_files[-1]
        dst_path = pf.root / filepath
        if not dst_path.exists() and src_path.exists() and src_path.resolve() != dst_path.resolve():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(dst_path))
    run_action(pf, state, "save", filepath=filepath, save_type=args.type)


def handle_context_backup(pf, state):
    err = validate_action(state, "context-backup")
    if err:
        print(display.error(err))
        sys.exit(1)
    version = state.context_version + 1
    try:
        backup_path = pf.backup_context(version)
        state, msg = execute_action(state, "context-backup")
        pf.save_state(state)
        print(msg)
        print(display.ok("backup created: " + str(backup_path)))
    except FileExistsError as e:
        print(display.error(str(e)))
        sys.exit(1)


# v1.5: new handlers

def handle_import_manuscript(pf, state, args):
    """원고 파일 임포트 → import_analysis 단계로 전환."""
    filepath = args.file
    # 프로젝트 루트 기준 상대경로 또는 절대경로 확인
    full_path = pf.root / filepath
    if not full_path.exists():
        full_path = Path(filepath)
    if not full_path.exists():
        print(display.error(f"파일을 찾을 수 없습니다: {filepath}"))
        sys.exit(1)
    run_action(pf, state, "import-manuscript", filepath=filepath)


def handle_import_context(pf, state):
    """기존 컨텍스트 파일 임포트 → Phase 2로 직행."""
    context_dir = pf.root / "context"
    if not context_dir.is_dir():
        print(display.error("context/ 디렉토리가 없습니다."))
        sys.exit(1)
    md_files = list(context_dir.glob("*.md"))
    if not md_files:
        print(display.error("context/ 디렉토리에 마크다운 파일이 없습니다."))
        sys.exit(1)
    for f in md_files:
        print(display.ok(f"컨텍스트 파일 발견: {f.name}"))
    run_action(pf, state, "import-context")


def handle_pd_proofread(pf, state, args):
    """PD 자체 퇴고 원고 등록 → 컨텍스트 갱신으로 직행."""
    filepath = args.file
    full_path = pf.root / filepath
    if not full_path.exists():
        full_path = Path(filepath)
    if not full_path.exists():
        print(display.error(f"파일을 찾을 수 없습니다: {filepath}"))
        sys.exit(1)
    run_action(pf, state, "pd-proofread", filepath=filepath)


def handle_merge_episode(pf, state):
    """장면 파일들을 하나의 에피소드로 병합."""
    err = validate_action(state, "merge-episode")
    if err:
        print(display.error(err))
        sys.exit(1)
    scene_files = [df for df in state.draft_files if Path(df).name.startswith("sc")]
    if not scene_files:
        print(display.error("병합할 장면 파일이 없습니다."))
        sys.exit(1)
    # 병합 전 누적 글자 수 검증
    total_chars = 0
    for sf in scene_files:
        sf_path = pf.root / sf
        if sf_path.exists():
            total_chars += ProjectFiles.count_story_chars(sf_path.read_text(encoding="utf-8"))
    if state.config.get("webnovel", True) and total_chars < MIN_STORY_CHARS:
        print(display.error(
            f"병합 불가: 누적 {total_chars:,}자 / 최소 {MIN_STORY_CHARS:,}자. "
            f"{MIN_STORY_CHARS - total_chars:,}자 추가 필요. 장면을 더 작성하세요."
        ))
        sys.exit(1)
    merged_path = pf.merge_scenes(scene_files)
    merged_rel = str(merged_path.relative_to(pf.root))
    state, msg = execute_action(state, "merge-episode", merged_file=merged_rel)
    pf.save_state(state)
    print(msg)
    # 병합 결과 글자 수 표시
    text = merged_path.read_text(encoding="utf-8")
    char_count = ProjectFiles.count_story_chars(text)
    if state.config.get("webnovel", True):
        print(display.ok(f"병합 결과: {char_count:,}자 (기준: {MIN_STORY_CHARS:,}자)"))
    else:
        print(display.ok(f"병합 결과: {char_count:,}자"))


def handle_revise_episode(pf, state, args):
    """v1.7: 완성된 에피소드를 수정 모드로 불러오기."""
    filename = args.file
    ep_path = pf.episodes_dir / filename
    if not ep_path.exists():
        print(display.error(f"에피소드 파일을 찾을 수 없습니다: episodes/{filename}"))
        sys.exit(1)
    content = ep_path.read_text(encoding="utf-8")
    draft_name = f"revision_{filename}"
    pf.save_draft(draft_name, content)
    print(display.ok(f"에피소드를 초안으로 복사: {draft_name}"))
    run_action(pf, state, "revise-episode", filepath=f"drafts/{draft_name}", original_episode=filename)


def handle_scenes(pf, state):
    """장면 목록과 글자 수 표시."""
    print(display.format_scenes(pf, state))


def handle_char_count(pf, state, args):
    """파일의 글자 수 표시. webnovel 모드일 때만 5500자 기준 표시."""
    filepath = Path(args.file)
    # 상대 경로면 프로젝트 루트 기준으로 해석
    if not filepath.is_absolute():
        filepath = pf.root / filepath
    if not filepath.exists():
        print(display.error(f"파일을 찾을 수 없습니다: {args.file}"))
        sys.exit(1)
    text = filepath.read_text(encoding="utf-8")
    char_count = ProjectFiles.count_story_chars(text)
    webnovel = state.config.get("webnovel", True)
    if webnovel:
        if char_count >= MIN_STORY_CHARS:
            print(display.ok(f"{filepath.name}: {char_count:,}자 (기준: {MIN_STORY_CHARS:,}자 충족)"))
        else:
            diff = MIN_STORY_CHARS - char_count
            print(display.error(f"{filepath.name}: {char_count:,}자 (기준: {MIN_STORY_CHARS:,}자 미달, {diff:,}자 부족)"))
    else:
        print(display.ok(f"{filepath.name}: {char_count:,}자"))


# v2.0: AI provider config handlers

def handle_ai_config(pf):
    """AI 프로바이더 설정 표시."""
    from .config import load_ai_config, format_config_summary
    config = load_ai_config(pf.root)
    print(format_config_summary(config))


def handle_ai_provider(pf, args):
    """Phase별 AI 프로바이더 설정."""
    from .config import load_ai_config, save_ai_config, PHASE_MAP

    config = load_ai_config(pf.root)
    provider_entry = {
        "type": args.provider_type,
        "model": args.model,
    }
    if args.api_key_env:
        provider_entry["api_key_env"] = args.api_key_env
    if args.base_url:
        provider_entry["base_url"] = args.base_url
    if args.temperature is not None:
        provider_entry["temperature"] = args.temperature
    if args.max_tokens is not None:
        provider_entry["max_tokens"] = args.max_tokens

    phase = args.phase.lower()
    if phase == "default":
        config["default_provider"] = provider_entry
        print(display.ok(f"기본 프로바이더 설정: {args.provider_type}/{args.model}"))
    else:
        # Accept both "phase1" and "phase1_planning" formats
        phase_key = PHASE_MAP.get(phase, phase)
        if phase_key not in config.get("phase_overrides", {}):
            print(display.error(f"알 수 없는 Phase: {phase}. 가능: default, phase1, phase2, phase3, phase4"))
            sys.exit(1)
        config["phase_overrides"][phase_key] = provider_entry
        print(display.ok(f"{phase_key} 프로바이더 설정: {args.provider_type}/{args.model}"))

    save_ai_config(pf.root, config)


def handle_ai_validate(pf):
    """모든 Phase의 AI 프로바이더 검증."""
    from .orchestrator import Orchestrator
    orch = Orchestrator(pf.root)
    errors = orch.validate_providers()
    if errors:
        for err in errors:
            print(display.error(err))
    else:
        print(display.ok("모든 프로바이더 설정이 유효합니다."))


def handle_ai_mode(pf):
    """standalone/passthrough 모드 표시 및 전환."""
    from .config import load_ai_config, save_ai_config
    config = load_ai_config(pf.root)
    mode = config.get("mode", "passthrough")
    print(f"현재 모드: {mode}")
    print("  standalone:   NF가 직접 AI API를 호출합니다.")
    print("  passthrough:  외부 AI(Claude Code 등)가 콘텐츠를 생성합니다.")
    print(f"변경하려면: nf config mode standalone|passthrough")


def handle_ai_cost(pf):
    """토큰 사용량 요약 표시."""
    from .cost_tracker import CostTracker
    tracker = CostTracker(pf.root)
    print(tracker.summary())


def handle_ai_cost_reset(pf):
    """비용 추적 로그 초기화."""
    from .cost_tracker import CostTracker
    tracker = CostTracker(pf.root)
    tracker.reset()
    print(display.ok("비용 추적 로그가 초기화되었습니다."))
