# -*- coding: utf-8 -*-
"""Interactive REPL for Novel Forge Claude."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from .models import ProjectState, Step
from .fileops import ProjectFiles, find_project_root
from .state import validate_action, execute_action, get_valid_actions
from . import display

TITLE_PATTERN = re.compile(r"^[a-zA-Z0-9_ -]+$")

NO_ARG_COMMANDS = frozenset({
    "status", "items", "next", "approve", "reject", "retry",
    "confirm-end", "context-update", "context-backup",
    "import-context", "switch-auto", "merge-episode", "scenes",
    "quit", "exit",
})

# Single-letter aliases for shortcuts
ALIASES = {
    "s": "select",
    "h": "hold",
    "d": "discard",
    "r": "retry",
    "a": "approve",
    "m": "revise",
    "c": "confirm-end",
}


def ask_title() -> str:
    """Prompt for novel title, validate English-only, return sanitized dir name."""
    while True:
        try:
            raw = input("Enter novel title (English only): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)

        if not raw:
            print(display.error("Title cannot be empty."))
            continue
        if not TITLE_PATTERN.match(raw):
            print(display.error("English letters, numbers, spaces, hyphens, and underscores only."))
            continue

        sanitized = re.sub(r"\s+", "_", raw).strip("_").lower()
        if not sanitized:
            print(display.error("Invalid title."))
            continue
        return sanitized


def load_or_create() -> tuple[ProjectFiles, ProjectState]:
    """Find existing project or create a new one."""
    root = find_project_root()
    if root is not None:
        pf = ProjectFiles.load(root)
        state = pf.read_state()
        print(display.ok(f"Loaded project: {state.project_name} ({root.name})"))
        return pf, state

    title = ask_title()
    base_dir = Path.cwd() / "projects"
    base_dir.mkdir(exist_ok=True)
    try:
        pf = ProjectFiles.create_project(base_dir, title, title)
    except FileExistsError as e:
        print(display.error(str(e)))
        raise SystemExit(1)

    state = pf.read_state()
    print(display.ok(f"Project created: {pf.root}"))
    print(display.step_msg("Phase 1: direction proposal"))
    print("  use 'add' to add directions")
    return pf, state


def parse_input(line: str) -> tuple[str, dict]:
    """Parse user input into (command, kwargs)."""
    line = line.strip()
    if not line:
        return "", {}

    # Split respecting quotes
    try:
        tokens = shlex.split(line)
    except ValueError:
        tokens = line.split()

    cmd = tokens[0].lower()
    rest = tokens[1:]

    # Resolve single-letter aliases
    if cmd in ALIASES:
        cmd = ALIASES[cmd]

    if cmd in NO_ARG_COMMANDS:
        return cmd, {}

    if cmd == "add":
        # add "text" -p 0.5  OR  add some text here
        text = None
        probability = None
        i = 0
        text_parts = []
        while i < len(rest):
            if rest[i] in ("-p", "--probability") and i + 1 < len(rest):
                try:
                    probability = float(rest[i + 1])
                except ValueError:
                    pass
                i += 2
                continue
            text_parts.append(rest[i])
            i += 1
        text = " ".join(text_parts) if text_parts else ""
        kwargs = {"text": text}
        if probability is not None:
            kwargs["probability"] = probability
        return "add", kwargs

    if cmd == "select":
        try:
            ids = [int(x) for x in rest]
        except ValueError:
            return cmd, {"_error": "Item IDs must be integers."}
        return "select", {"item_ids": ids}

    if cmd in ("hold", "discard"):
        if not rest:
            return cmd, {"_error": f"Usage: {cmd} <id>"}
        try:
            item_id = int(rest[0])
        except ValueError:
            return cmd, {"_error": "Item ID must be an integer."}
        return cmd, {"item_id": item_id}

    if cmd == "revise":
        feedback = " ".join(rest) if rest else ""
        return "revise", {"feedback": feedback}

    if cmd == "config":
        if len(rest) < 2:
            return cmd, {"_error": "Usage: config <key> <value>"}
        return "config", {"key": rest[0], "value": rest[1]}

    if cmd == "save":
        if len(rest) < 2:
            return cmd, {"_error": "Usage: save <plan|manuscript|proofread> <filepath>"}
        return "save", {"filepath": rest[1]}

    # v1.5: import-manuscript
    if cmd == "import-manuscript":
        if not rest:
            return cmd, {"_error": "Usage: import-manuscript <filepath>"}
        return "import-manuscript", {"filepath": rest[0]}

    # v1.5: pd-proofread
    if cmd == "pd-proofread":
        if not rest:
            return cmd, {"_error": "Usage: pd-proofread <filepath>"}
        return "pd-proofread", {"filepath": rest[0]}

    # Unknown command
    return cmd, {}


def resolve_context_alias(cmd: str, state: ProjectState) -> str:
    """Resolve ambiguous aliases (D, R) based on current step."""
    review_steps = {
        Step.PLAN_DECISION.value,
        Step.WRITING_DECISION.value,
        Step.PROOFREAD_DECISION.value,
        Step.DEVELOPMENT_CONFIRM.value,
        Step.IMPORT_REVIEW.value,
        Step.SCENE_DECISION.value,
    }
    if cmd == "discard" and state.step in review_steps:
        return "reject"
    if cmd == "retry" and state.step == Step.DEVELOPMENT_CONFIRM.value:
        return "reject"
    return cmd


def handle_command(pf: ProjectFiles, state: ProjectState, cmd: str, kwargs: dict) -> ProjectState:
    """Execute a single command and return updated state."""
    if "_error" in kwargs:
        print(display.error(kwargs["_error"]))
        return state

    # Resolve D/R aliases based on current step
    cmd = resolve_context_alias(cmd, state)

    if cmd == "status":
        print(display.format_status(state))
        return state

    if cmd == "items":
        print(display.format_items(state))
        return state

    # scenes: 장면 목록 표시 (상태 변경 없음)
    if cmd == "scenes":
        print(display.format_scenes(pf, state))
        return state

    # merge-episode needs special handling (file merge + state update)
    if cmd == "merge-episode":
        from .fileops import ProjectFiles as _PF
        err = validate_action(state, "merge-episode")
        if err:
            print(display.error(err))
            return state
        scene_files = [df for df in state.draft_files if Path(df).name.startswith("sc")]
        if not scene_files:
            print(display.error("병합할 장면 파일이 없습니다."))
            return state
        # 병합 전 누적 글자 수 검증
        total_chars = 0
        for sf in scene_files:
            sf_path = pf.root / sf
            if sf_path.exists():
                total_chars += _PF.count_story_chars(sf_path.read_text(encoding="utf-8"))
        if total_chars < 5500:
            print(display.error(
                f"병합 불가: 누적 {total_chars:,}자 / 최소 5,500자. "
                f"{5500 - total_chars:,}자 추가 필요. 장면을 더 작성하세요."
            ))
            return state
        merged_path = pf.merge_scenes(scene_files)
        merged_rel = str(merged_path.relative_to(pf.root))
        state, msg = execute_action(state, "merge-episode", merged_file=merged_rel)
        pf.save_state(state)
        print(msg)
        # 병합 결과 글자 수 표시
        text = merged_path.read_text(encoding="utf-8")
        char_count = _PF.count_story_chars(text)
        print(display.ok(f"병합 결과: {char_count:,}자 (기준: 5,500자)"))
        return state

    # context-backup needs special handling (file backup + state update)
    if cmd == "context-backup":
        err = validate_action(state, "context-backup")
        if err:
            print(display.error(err))
            return state
        version = state.context_version + 1
        try:
            backup_path = pf.backup_context(version)
            state, msg = execute_action(state, "context-backup")
            pf.save_state(state)
            print(msg)
            print(display.ok("backup created: " + str(backup_path)))
        except FileExistsError as e:
            print(display.error(str(e)))
        return state

    # next needs special handling (episode auto-save)
    if cmd == "next":
        if state.step == Step.COMPLETE.value and state.draft_files:
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

    # v1.5: import-context needs filesystem validation
    if cmd == "import-context":
        context_dir = pf.root / "context"
        if not context_dir.is_dir():
            print(display.error("context/ 디렉토리가 없습니다."))
            return state
        md_files = list(context_dir.glob("*.md"))
        if not md_files:
            print(display.error("context/ 디렉토리에 마크다운 파일이 없습니다."))
            return state
        for f in md_files:
            print(display.ok(f"컨텍스트 파일 발견: {f.name}"))

    # v1.5: import-manuscript needs file validation
    if cmd == "import-manuscript":
        filepath = kwargs.get("filepath", "")
        full_path = pf.root / filepath
        if not full_path.exists():
            full_path = Path(filepath)
        if not full_path.exists():
            print(display.error(f"파일을 찾을 수 없습니다: {filepath}"))
            return state

    # v1.5: pd-proofread needs file validation
    if cmd == "pd-proofread":
        filepath = kwargs.get("filepath", "")
        full_path = pf.root / filepath
        if not full_path.exists():
            full_path = Path(filepath)
        if not full_path.exists():
            print(display.error(f"파일을 찾을 수 없습니다: {filepath}"))
            return state

    # General action flow
    err = validate_action(state, cmd, **kwargs)
    if err:
        print(display.error(err))
        return state

    state, msg = execute_action(state, cmd, **kwargs)
    pf.save_state(state)
    print(msg)
    return state


def print_header(state: ProjectState) -> None:
    """Print a compact status header."""
    phase_label = display.PHASE_LABELS.get(state.phase, state.phase)
    step_label = display.STEP_LABELS.get(state.step, state.step)
    actions = get_valid_actions(state)
    print(f"\n[{phase_label} > {step_label}]")
    if actions:
        print(f"  commands: {', '.join(actions)}")


def run() -> None:
    """Main interactive loop."""
    print("=== Novel Forge Claude (Interactive) ===\n")
    pf, state = load_or_create()

    while True:
        print_header(state)
        try:
            line = input("\nnfc> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not line:
            continue

        cmd, kwargs = parse_input(line)

        if cmd in ("quit", "exit"):
            print("Bye!")
            break

        if cmd == "":
            continue

        # Check if it's a known command
        known = NO_ARG_COMMANDS | {
            "add", "select", "hold", "discard", "revise", "config", "save",
            "import-manuscript", "pd-proofread", "merge-episode", "scenes",
        }
        if cmd not in known:
            print(display.error(f"Unknown command: {cmd}"))
            print(f"  Available: {', '.join(sorted(known - {'quit', 'exit'}))}")
            continue

        state = handle_command(pf, state, cmd, kwargs)
