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
    p_init.add_argument("name", nargs="?", default=None,
                        help="project name (ASCII ok; 한글은 --name-file 권장)")
    p_init.add_argument("--title", help="english dir name", default=None)
    p_init.add_argument("--name-file", default=None,
                        help="UTF-8 파일에서 프로젝트명을 읽음 (Windows 비ASCII 안전)")
    p_init.add_argument("--type", dest="work_type", choices=["novel", "comic"], default="novel",
                        help="작품 유형 (novel=웹소설, comic=만화 스토리보드)")

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
    p_backup_ep = sub.add_parser("backup-episode", help="backup episode file")
    p_backup_ep.add_argument("file", help="episode file (e.g. ep003.md or 3)")
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

    # v2.2: Phase 2 앙상블 (외부 CLI worker 병렬)
    p_ens = sub.add_parser("ensemble-dev", help="v2.2: Phase 2 앙상블 전개안 (외부 CLI 병렬)")
    p_ens.add_argument(
        "--workers",
        default=None,
        help="쉼표구분 worker 타입 (기본: gemini-cli,codex-cli)",
    )

    # v2.3: 집필 파이프라인 (Gemini 초고 → Codex 1차 퇴고 → Claude 2차)
    p_pipe = sub.add_parser("draft-pipeline", help="v2.3: 릴레이 집필 (초고→1차퇴고 자동)")
    p_pipe.add_argument("--draft", default=None, help="초고 worker 타입 (기본: gemini-cli)")
    p_pipe.add_argument("--revise", default=None, help="1차 퇴고 worker 타입 (기본: codex-cli)")

    p_room = sub.add_parser("draft-room", help="v2.8: 6에이전트 작가실 릴레이 집필 (발상→증폭→조율)")
    p_room.add_argument("--gemini", default=None, help="발상 단계(G1·G2) worker 타입 (기본: gemini-cli)")
    p_room.add_argument("--codex", default=None, help="증폭 단계(C1·C2) worker 타입 (기본: codex-cli)")

    # v2.4: 재미/취향 학습 토대
    p_taste = sub.add_parser("taste-init", help="v2.4: 취향 프로파일 시드 (context/taste_profile.md)")
    p_taste.add_argument("--force", action="store_true", help="기존 프로파일 덮어쓰기")

    # v2.4: 학습 루프 (신호 → 프로파일 갱신 제안 → 적용)
    p_tlearn = sub.add_parser("taste-learn", help="v2.4: 신호를 정제해 프로파일 갱신 제안 생성")
    p_tlearn.add_argument("--worker", default=None, help="reflection worker 타입 (기본: gemini-cli)")
    sub.add_parser("taste-apply", help="v2.4: 갱신 제안을 프로파일에 적용 (이전 버전 백업)")

    # v2.5: 뻔함 가드 (Phase 2 제안 항목을 취향 기준으로 채점)
    p_guard = sub.add_parser("cliche-guard", help="v2.5: 제안 항목의 뻔함 심사 (취향 기준)")
    p_guard.add_argument("--worker", default=None, help="심사 worker 타입 (기본: codex-cli)")

    # v2.6: 재미 보존 diff 가드 (퇴고 전후 재미 손실 검출)
    p_fdiff = sub.add_parser("fun-diff", help="v2.6: 초고 vs 퇴고본 재미 보존 검수")
    p_fdiff.add_argument("before", help="BEFORE 원고 경로 (초고/직전)")
    p_fdiff.add_argument("after", help="AFTER 원고 경로 (퇴고본)")
    p_fdiff.add_argument("--worker", default=None, help="검수 worker 타입 (기본: codex-cli)")

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


MIN_STORY_CHARS = 5700


def check_draft_length(pf, state):
    """writing_decision 단계에서 approve 시 draft 분량 검증."""
    if state.step != Step.WRITING_DECISION.value:
        return None
    if not state.draft_files:
        return None
    if state.work_type == "comic":
        if not state.config.get("webnovel", True):
            return None  # 자유 모드(webnovel=false): 분량 하한 게이트 비활성
        target = state.config.get("comic_pages_per_episode", 18)
        for df in state.draft_files:
            draft_path = pf.root / df
            if not draft_path.exists():
                continue
            pages = ProjectFiles.count_pages(draft_path.read_text(encoding="utf-8"))
            if pages < target:
                return (
                    f"원고 분량 미달: {df} ({pages}/{target}페이지). "
                    f"{target - pages}페이지 추가 필요."
                )
        return None
    if not state.config.get("webnovel", True):
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
        from .taste import log_signal, item_brief
        _disc = state.get_item(args.id)
        _disc_brief = item_brief(_disc) if _disc else None
        run_action(pf, state, "discard", item_id=args.id)
        if _disc_brief:
            log_signal(pf.root, state, "discard", item=_disc_brief)
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
        from .taste import log_signal
        log_signal(pf.root, state, "revise", feedback=(args.feedback or "")[:1000])
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
    elif args.command == "backup-episode":
        handle_backup_episode(pf, args)
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
    elif args.command == "ensemble-dev":
        handle_ensemble_dev(pf, state, args)
    elif args.command == "draft-pipeline":
        handle_draft_pipeline(pf, state, args)
    elif args.command == "draft-room":
        handle_draft_room(pf, state, args)
    elif args.command == "taste-init":
        handle_taste_init(pf, args)
    elif args.command == "taste-learn":
        handle_taste_learn(pf, state, args)
    elif args.command == "taste-apply":
        handle_taste_apply(pf)
    elif args.command == "cliche-guard":
        handle_cliche_guard(pf, state, args)
    elif args.command == "fun-diff":
        handle_fun_diff(pf, state, args)
    else:
        parser.print_help()


def handle_select(pf, state, item_ids):
    """select 처리 + 미선정 active 항목을 자동 shelve."""
    from .taste import log_signal, item_brief
    selected_set = set(item_ids)
    # 취향 신호: 무엇을 골랐고 무엇을 버렸는가 (상태 변경 전에 캡처)
    decision_step = state.step  # run_action 전이 전 결정 시점 step
    chosen = [item_brief(i) for i in state.items if i.id in selected_set]
    rejected = [item_brief(i) for i in state.items
                if i.id not in selected_set and i.status == ItemStatus.PROPOSED.value]
    # 선정 전에 나머지 active 항목을 shelve
    if state.step in (Step.DIRECTION_DECISION.value, Step.DEVELOPMENT_DECISION.value):
        for item in state.items:
            if item.id not in selected_set and item.status == ItemStatus.PROPOSED.value:
                item.status = ItemStatus.HELD.value
                prefix = "idea" if state.phase == Phase.PHASE1.value else "dev"
                shelve_path = pf.save_to_shelve(item.text, item.id, prefix, item.probability)
                print(display.ok(f"자동 보류: {display.format_item_short(item)} → {shelve_path.name}"))
    run_action(pf, state, "select", item_ids=item_ids)
    log_signal(pf.root, state, "select", step=decision_step, chosen=chosen, rejected=rejected)


def handle_hold(pf, state, item_id):
    """v1.7: hold 처리 + shelve 저장."""
    from .taste import log_signal, item_brief
    # writing_decision hold → draft를 shelve로 보류
    if state.step == Step.WRITING_DECISION.value:
        log_signal(pf.root, state, "hold_draft")
        _handle_writing_hold(pf, state)
        return
    # Phase 1/2 item hold + shelve 저장
    item = state.get_item(item_id)
    brief = item_brief(item) if item else None
    run_action(pf, state, "hold", item_id=item_id)
    if brief:
        log_signal(pf.root, state, "hold", item=brief)
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
    # Windows 셸(PowerShell 5.1/git-bash)은 비ASCII argv를 코드페이지로 손실시킨다.
    # 한글 프로젝트명은 --name-file(UTF-8)로 전달해야 안전하다.
    name = args.name
    name_file = getattr(args, "name_file", None)
    if name_file:
        nf_path = Path(name_file)
        if not nf_path.exists():
            print(display.error(f"--name-file 경로를 찾을 수 없습니다: {name_file}"))
            sys.exit(1)
        name = nf_path.read_text(encoding="utf-8").strip()
    if not name:
        print(display.error("프로젝트명이 필요합니다. (name 인자 또는 --name-file)"))
        sys.exit(1)
    if "�" in name:
        print(display.error(
            "프로젝트명에 깨진 문자(U+FFFD)가 있습니다. "
            "한글 이름은 셸 인자 대신 --name-file <UTF-8 파일>로 전달하세요."
        ))
        sys.exit(1)
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
        pf = ProjectFiles.create_project(base_dir, name, title, work_type=getattr(args, "work_type", "novel"))
        from .taste import seed_profile
        seed_profile(pf.root)
        print(display.ok("project created: " + str(pf.root)))
        if getattr(args, "work_type", "novel") == "comic":
            print(display.step_msg("작품 유형: 만화 스토리보드 (산출물=페이지/컷 콘티)"))
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
            import re
            pd_num = state.episode_count + 1
            auto_num = state.episode_count + 1
            for df in list(dict.fromkeys(state.draft_files)):
                draft_path = pf.root / df
                filename = Path(df).name
                is_auto = filename.startswith("auto_")
                # episodes 디렉토리에는 항상 ep### 형식으로 저장
                prefix = "ep"
                # draft 파일명에서 에피소드 번호 추출 (auto_ep012.md → 12)
                match = re.search(r'(?:auto_)?ep(\d+)', filename)
                if match:
                    episode_num = int(match.group(1))
                elif is_auto:
                    episode_num = auto_num
                    auto_num += 1
                else:
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


def handle_backup_episode(pf, args):
    """에피소드 파일 백업."""
    import re
    file_arg = args.file

    # 숫자만 입력된 경우 ep###.md로 변환
    if re.match(r'^\d+$', file_arg):
        episode_file = f"ep{int(file_arg):03d}.md"
    elif not file_arg.endswith('.md'):
        episode_file = f"{file_arg}.md"
    else:
        episode_file = file_arg

    try:
        backup_path = pf.backup_episode(episode_file)
        print(display.ok(f"백업 완료: {backup_path.name}"))
    except FileNotFoundError as e:
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
    # 취향 신호: PD 직접 편집 — 직전 AI 초안 → PD 퇴고본 diff (difflib, AI 호출 없음)
    try:
        if state.draft_files:
            ai_draft = pf.root / state.draft_files[-1]
            if ai_draft.exists():
                from .pd_edit import summarize_edit
                from .taste import log_signal
                edit = summarize_edit(
                    ai_draft.read_text(encoding="utf-8"),
                    full_path.read_text(encoding="utf-8"),
                )
                log_signal(
                    pf.root, state, "pd_edit",
                    removed=edit["removed"], added=edit["added"],
                    removed_count=edit["removed_count"], added_count=edit["added_count"],
                )
                print(display.ok(
                    f"PD 편집 신호 기록: 뺌 {edit['removed_count']}줄 / 넣음 {edit['added_count']}줄"
                ))
    except Exception:
        pass  # 신호 캡처 실패가 pd-proofread를 막아선 안 됨
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
    merged_path = pf.merge_scenes(scene_files)
    merged_rel = str(merged_path.relative_to(pf.root))
    state, msg = execute_action(state, "merge-episode", merged_file=merged_rel)
    pf.save_state(state)
    print(msg)
    # 병합 결과 글자 수 표시
    text = merged_path.read_text(encoding="utf-8")
    if state.work_type == "comic":
        pages = ProjectFiles.count_pages(text)
        cuts = ProjectFiles.count_cuts(text)
        target = state.config.get("comic_pages_per_episode", 18)
        print(display.ok(f"병합 결과: {pages}/{target}페이지 (총 {cuts}컷)"))
    else:
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


def handle_ensemble_dev(pf, state, args):
    """v2.2: Phase 2 앙상블 — 외부 CLI worker를 병렬 실행해 전개안 후보를 drafts/에 생성.

    하이브리드 모드: NF는 fan-out과 파일 저장만 담당하고, 자기 배치 추가·최종
    큐레이션은 라이브 Claude Code 세션이 PD와 함께 수행한다.
    """
    from .ensemble import run_ensemble_developments, DEFAULT_WORKERS

    if state.phase != Phase.PHASE2.value:
        print(display.error(f"앙상블 전개안은 Phase 2에서만 사용합니다 (현재 {state.phase})."))
        sys.exit(1)

    workers = None
    if getattr(args, "workers", None):
        workers = [{"type": t.strip(), "model": ""} for t in args.workers.split(",") if t.strip()]
    used = workers or DEFAULT_WORKERS
    names = ", ".join(w["type"] for w in used)
    print(f"앙상블 전개안 생성 중 (병렬): {names} ...")

    results = run_ensemble_developments(pf.root, state, workers=workers)

    print()
    any_ok = False
    for r in results:
        if r["ok"]:
            any_ok = True
            print(display.ok(f"{r['type']}: 전개안 {r['options']}개 / {r['chars']:,}자 → {r['path'].name}"))
        else:
            print(display.error(f"{r['type']}: 실패 — {r['error']}"))

    if not any_ok:
        print(display.error("모든 worker가 실패했습니다. CLI 설치/로그인 상태를 확인하세요."))
        sys.exit(1)

    print()
    print("다음 단계 (하이브리드 큐레이션):")
    print("  1) drafts/ensemble_dev_*.md 를 읽습니다.")
    print("  2) Claude Code가 자체 전개안 배치를 추가로 생성합니다.")
    print("  3) source(gemini/codex/claude)별로 모아 PD에게 전체 제시합니다.")
    print("  4) PD 선택분을 'nf add'로 등록 → 'nf select'로 확정합니다.")


def handle_taste_init(pf, args):
    """v2.4: 취향 프로파일 시드/재시드."""
    from .taste import seed_profile, profile_path
    created = seed_profile(pf.root, force=bool(getattr(args, "force", False)))
    p = profile_path(pf.root)
    rel = p.relative_to(pf.root)
    if created:
        print(display.ok(f"취향 프로파일 시드: {rel}"))
    else:
        print(display.ok(f"이미 존재합니다: {rel} (덮어쓰려면 --force)"))


def handle_taste_learn(pf, state, args):
    """v2.4: 신호를 정제해 프로파일 갱신 제안을 생성 (적용은 taste-apply)."""
    from .taste_learn import run_taste_learn, DEFAULT_WORKER

    worker = {"type": args.worker.strip(), "model": "", "timeout": 600} if getattr(args, "worker", None) else None
    wname = (worker or DEFAULT_WORKER)["type"]
    print(f"취향 학습 중 (reflection worker: {wname}) — 신호 정제 → 갱신 제안 ...")

    result = run_taste_learn(pf.root, worker=worker)
    if not result.get("ok"):
        print(display.error(f"학습 실패: {result.get('reason')}"))
        sys.exit(1)

    prop_rel = result["proposal_path"].relative_to(pf.root)
    print(display.ok(f"신호 {result['signal_count']}건 정제 → 제안 생성: {prop_rel}"))
    print()
    print("다음 단계:")
    print(f"  1) {prop_rel} 를 현재 context/taste_profile.md와 비교 검토 (Claude Code가 PD에게 제시)")
    print("  2) 승인하면 'nf taste-apply'로 적용 (이전 버전은 backup/에 보존)")


def handle_taste_apply(pf):
    """v2.4: 갱신 제안을 프로파일에 적용 (이전 버전 백업)."""
    from .taste_learn import apply_proposal

    result = apply_proposal(pf.root)
    if not result.get("ok"):
        print(display.error(f"적용 실패: {result.get('reason')}"))
        sys.exit(1)

    applied_rel = result["applied"].relative_to(pf.root)
    print(display.ok(f"프로파일 적용: {applied_rel}"))
    if result.get("backup"):
        print(display.ok(f"이전 버전 백업: {result['backup'].relative_to(pf.root)}"))


def handle_cliche_guard(pf, state, args):
    """v2.5: 제안 항목(PROPOSED)을 취향 프로파일 기준으로 뻔함 심사."""
    from .cliche_guard import run_cliche_guard, DEFAULT_WORKER
    from .taste import item_brief

    items = [item_brief(i) for i in state.items if i.status == ItemStatus.PROPOSED.value]
    if not items:
        print(display.error("심사할 제안 항목이 없습니다. (add로 옵션을 먼저 등록하세요)"))
        sys.exit(1)

    worker = {"type": args.worker.strip(), "model": "", "timeout": 300} if getattr(args, "worker", None) else None
    wname = (worker or DEFAULT_WORKER)["type"]
    print(f"뻔함 심사 중 (worker: {wname}) — {len(items)}개 옵션 채점 ...")

    result = run_cliche_guard(pf.root, items, worker=worker)
    if not result.get("ok"):
        print(display.error(f"심사 실패: {result.get('reason')}"))
        sys.exit(1)

    parsed = result.get("parsed")
    if not parsed:
        print(display.error("심사 결과 파싱 실패. 원문 일부:"))
        print((result.get("raw") or "")[:1500])
        sys.exit(1)

    print()
    for o in parsed.get("options", []):
        print(
            f"  [{o.get('id')}] 의외 {o.get('의외성')} · 개연 {o.get('개연성')} · "
            f"매력 {o.get('매력')} · 뻔함 {o.get('뻔함')}  — {o.get('평', '')}"
        )
    print()
    print(f"총평: {parsed.get('verdict', '')}")
    if result.get("too_safe"):
        print(display.error("⚠ 전개안이 전반적으로 너무 안전합니다 (김빠짐 위험)."))
        if parsed.get("suggestion"):
            print(f"제안: {parsed.get('suggestion')}")
        print("→ 'retry'로 재생성하거나, 회피 패턴을 피한 더 과감한 안을 추가하세요.")
    else:
        print(display.ok("신선한 선택지가 존재합니다."))
        if parsed.get("suggestion"):
            print(f"보완 제안: {parsed.get('suggestion')}")


def handle_fun_diff(pf, state, args):
    """v2.6: 초고(BEFORE) vs 퇴고본(AFTER)의 재미 손실 검수."""
    from .fun_diff import run_fun_diff, DEFAULT_WORKER

    def _resolve(p):
        pp = Path(p)
        return pp if pp.is_absolute() else (pf.root / p)

    before = _resolve(args.before)
    after = _resolve(args.after)
    worker = {"type": args.worker.strip(), "model": "", "timeout": 600} if getattr(args, "worker", None) else None
    wname = (worker or DEFAULT_WORKER)["type"]
    print(f"재미 보존 검수 중 (worker: {wname}) — {before.name} → {after.name} ...")

    result = run_fun_diff(pf.root, before, after, worker=worker)
    if not result.get("ok"):
        print(display.error(f"검수 실패: {result.get('reason')}"))
        sys.exit(1)

    parsed = result.get("parsed")
    if not parsed:
        print(display.error("검수 결과 파싱 실패. 원문 일부:"))
        print((result.get("raw") or "")[:1500])
        sys.exit(1)

    print()
    regs = parsed.get("regressions") or []
    if regs:
        for r in regs:
            print(f"  [심각도 {r.get('심각도')}] {r.get('요소')}")
            print(f"     before: {r.get('before')}")
            print(f"     after : {r.get('after')}")
            print(f"     복원  : {r.get('복원제안')}")
    else:
        print("  (감지된 재미 손실 없음)")

    pw = parsed.get("preserved_well") or []
    if pw:
        print(f"\n잘 보존됨: {', '.join(str(x) for x in pw)}")
    print(f"\n총평: {parsed.get('verdict', '')}")

    if result.get("regressed"):
        print(display.error("⚠ 퇴고에서 재미 요소가 감축됐습니다. 복원 제안을 검토하세요."))
    else:
        print(display.ok("재미 손실 없음 — 퇴고가 재미를 보존했습니다."))


def handle_draft_pipeline(pf, state, args):
    """v2.3: 집필 파이프라인 — Gemini 초고 → Codex 1차 퇴고 자동 실행.

    2차 퇴고(컨텍스트 정합성)와 최종 승인은 라이브 Claude Code 세션이 수행한다.
    """
    from .pipeline import run_draft_pipeline, DEFAULT_DRAFT_WORKER, DEFAULT_REVISE_WORKER

    if not state.selected_developments:
        print(display.error("선정된 전개가 없습니다. Phase 2에서 전개를 먼저 선정하세요."))
        sys.exit(1)

    draft_worker = {"type": args.draft.strip(), "model": "", "timeout": 900} if getattr(args, "draft", None) else None
    revise_worker = {"type": args.revise.strip(), "model": "", "timeout": 600} if getattr(args, "revise", None) else None

    d_name = (draft_worker or DEFAULT_DRAFT_WORKER)["type"]
    r_name = (revise_worker or DEFAULT_REVISE_WORKER)["type"]
    ep_num = state.episode_count + 1
    print(f"집필 파이프라인 시작 (ep{ep_num:03d}): 초고={d_name} → 1차퇴고={r_name} ...")

    result = run_draft_pipeline(pf.root, state, draft_worker=draft_worker, revise_worker=revise_worker)

    print()
    for s in result["stages"]:
        if s["ok"]:
            print(display.ok(f"{s['stage']} ({s['model']}): {s['chars']:,}자 → {s['path'].name}"))
        else:
            print(display.error(f"{s['stage']} ({s['model']}): 실패 — {s['error']}"))

    making_rel = result["making_dir"].relative_to(pf.root)
    if not result["ready_for_stage3"]:
        print(display.error("초고/1차 퇴고가 완료되지 않았습니다. 위 오류를 확인하세요."))
        sys.exit(1)

    print()
    print(f"히스토리: {making_rel}/ (전 단계 보존, 덮어쓰기 없음)")
    print()
    print("다음 단계 (2차 퇴고 + 승인, Claude Code):")
    print(f"  1) {making_rel}/02_revise1_codex.md 를 읽습니다.")
    print("  2) 컨텍스트 정합성(플롯/캐릭터/복선 충돌)을 검수하여")
    print(f"     {making_rel}/03_revise2_claude.md 로 저장합니다.")
    print("  3) PD에게 제시: [A]승인 / [M]수정 / [D]폐기")
    print(f"  4) A → episodes/ep{ep_num:03d}.md 로 승격 후 컨텍스트 갱신(Phase 4)으로 진행")


def handle_draft_room(pf, state, args):
    """v2.8: 작가실 릴레이 — G1광인→G2씨앗→C1판돈→C2디테일 자동, K1~K3은 라이브 Claude."""
    from .pipeline import run_draft_room, DEFAULT_ROOM_GEMINI, DEFAULT_ROOM_CODEX

    if not state.selected_developments:
        print(display.error("선정된 전개가 없습니다. Phase 2에서 전개를 먼저 선정하세요."))
        sys.exit(1)

    gemini_worker = {"type": args.gemini.strip(), "model": "", "timeout": 900} if getattr(args, "gemini", None) else None
    codex_worker = {"type": args.codex.strip(), "model": "", "timeout": 900} if getattr(args, "codex", None) else None

    g_name = (gemini_worker or DEFAULT_ROOM_GEMINI)["type"]
    c_name = (codex_worker or DEFAULT_ROOM_CODEX)["type"]
    ep_num = state.episode_count + 1
    print(f"작가실 릴레이 시작 (ep{ep_num:03d}): G1·G2={g_name} → C1·C2={c_name} ...")

    result = run_draft_room(pf.root, state, gemini_worker=gemini_worker, codex_worker=codex_worker)

    print()
    for s in result["stages"]:
        if s["ok"]:
            print(display.ok(f"{s['stage']} ({s['model']}): {s['chars']:,}자 → {s['path'].name}"))
        else:
            print(display.error(f"{s['stage']} ({s['model']}): 실패 — {s['error']}"))

    making_rel = result["making_dir"].relative_to(pf.root)
    if not result["ready_for_live"]:
        print(display.error("자동 릴레이(G1~C2)가 완료되지 않았습니다. 위 오류를 확인하세요."))
        sys.exit(1)

    print()
    print(f"히스토리: {making_rel}/ (전 단계 보존, 덮어쓰기 없음)")
    print()
    print("다음 단계 (라이브 조율 K1→K2→K3, Claude Code):")
    print(f"  1) {making_rel}/04_c2_detail.md 를 읽습니다.")
    print("  2) K1 톤조율: 폭주 에너지를 톤·리듬에 맞게 깎되 재미는 보존 → 05_k1_tone.md")
    print("  3) K2 정합성감사: 플롯·캐릭터·복선 충돌 검수·수선 → 06_k2_audit.md")
    print("  4) K3 교정: 맞춤법·오탈자·띄어쓰기·비문 라인 레벨 일소 (맨 마지막) → 07_k3_copyedit.md")
    print(f"  5) 재미 보존 점검: python nf.py fun-diff {making_rel}/04_c2_detail.md {making_rel}/07_k3_copyedit.md")
    print("  6) PD에게 제시: [A]승인 / [M]수정 / [D]폐기")
    print(f"  7) A → episodes/ep{ep_num:03d}.md 로 승격 후 컨텍스트 갱신(Phase 4)으로 진행")
