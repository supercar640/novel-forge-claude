# -*- coding: utf-8 -*-
"""argparse CLI routing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .models import ProjectState, Step
from .fileops import ProjectFiles, find_project_root
from .state import validate_action, execute_action, get_valid_actions
from . import display


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfc",
        description="Novel Forge Claude - CLI",
    )
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

    p_hold = sub.add_parser("hold", help="hold item")
    p_hold.add_argument("id", type=int, help="item ID")

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

    # v1.5: new commands
    p_import_ms = sub.add_parser("import-manuscript", help="import manuscript for analysis")
    p_import_ms.add_argument("file", help="manuscript file path")

    sub.add_parser("import-context", help="import existing context files")

    p_pd_proofread = sub.add_parser("pd-proofread", help="register PD proofread manuscript")
    p_pd_proofread.add_argument("file", help="proofread file path")

    sub.add_parser("switch-auto", help="switch to auto writing mode")

    return parser


def load_project():
    root = find_project_root()
    if root is None:
        print(display.error("project not found. use 'nfc init <name>'"))
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


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        handle_init(args)
        return

    pf, state = load_project()

    if args.command == "status":
        print(display.format_status(state))
    elif args.command == "items":
        print(display.format_items(state))
    elif args.command == "add":
        run_action(pf, state, "add", text=args.text, probability=args.probability)
    elif args.command == "select":
        run_action(pf, state, "select", item_ids=args.ids)
    elif args.command == "hold":
        run_action(pf, state, "hold", item_id=args.id)
    elif args.command == "discard":
        run_action(pf, state, "discard", item_id=args.id)
    elif args.command == "retry":
        run_action(pf, state, "retry")
    elif args.command == "approve":
        err = check_draft_length(pf, state)
        if err:
            print(display.error(err))
            sys.exit(1)
        run_action(pf, state, "approve")
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
    elif args.command == "merge-episode":
        handle_merge_episode(pf, state)
    elif args.command == "scenes":
        handle_scenes(pf, state)
    else:
        parser.print_help()


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
    run_action(pf, state, "save", filepath=filepath)


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
    if total_chars < MIN_STORY_CHARS:
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
    print(display.ok(f"병합 결과: {char_count:,}자 (기준: {MIN_STORY_CHARS:,}자)"))


def handle_scenes(pf, state):
    """장면 목록과 글자 수 표시."""
    print(display.format_scenes(pf, state))
