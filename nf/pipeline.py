"""집필 파이프라인 — 역할 분담형 릴레이 집필.

3단 릴레이:
  1) 초고     : Gemini  — 전개+컨텍스트 기반으로 빠르게 한 회차를 갈겨씀 (분량·기세 우선)
  2) 1차 퇴고 : Codex   — 맞춤법·오탈자·비문, 문장 다듬기, 설정 표기 오류 (라인 레벨)
  3) 2차 퇴고 : Claude Code(라이브) — 컨텍스트 정합성 검수 + PD 최종 승인 (이 모듈 밖)

하이브리드: 이 모듈은 외부 CLI 단계(1·2)를 자동 실행하고 결과를 ep###_making/에
기록한다. 3단계와 최종 승인은 라이브 Claude Code 세션이 PD와 함께 수행한다.
모든 산출물은 새 파일로 남기며 덮어쓰지 않는다 (제작 히스토리 보존).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .agents.base_agent import PhaseAgent
from .agents.writing_agent import WritingAgent
from .agents.revision_agent import RevisionAgent
from .config import create_provider

# 집필은 5,500자+ 본문이라 전개안 생성보다 훨씬 오래 걸린다 → 넉넉한 타임아웃.
DEFAULT_DRAFT_WORKER = {"type": "gemini-cli", "model": "", "timeout": 900}
DEFAULT_REVISE_WORKER = {"type": "codex-cli", "model": "", "timeout": 600}

# 초고(Gemini)용 추가 지시 — "막 갈김": 다듬기보다 분량·기세·완결.
DRAFT_INSTRUCTIONS = (
    "이것은 **초고**입니다. 다듬기보다 분량과 기세를 우선하세요.\n"
    "- 멈추지 말고 회차를 끝까지 완성하세요 (최소 5,500자).\n"
    "- 맞춤법·표현의 세련됨은 신경 쓰지 마세요 (후속 퇴고가 처리합니다).\n"
    "- 전개를 시원하게 밀어붙이고 장면을 충분히 살리세요."
)


def _stage_header(stage: str, model: str, ep_num: int, source: Optional[str], chars: int) -> str:
    """제작 파일 머리말 (HTML 주석 → 본문 렌더링에 영향 없음)."""
    return (
        "<!--\n"
        f"stage: {stage}\n"
        f"model: {model}\n"
        f"episode: {ep_num}\n"
        f"created: {datetime.now().isoformat(timespec='seconds')}\n"
        f"source: {source or '(none)'}\n"
        f"chars: {chars:,}\n"
        "-->\n\n"
    )


def _versioned_path(directory: Path, stem: str) -> Path:
    """히스토리 보존: 같은 이름이 있으면 _r2, _r3… 로 적층."""
    path = directory / f"{stem}.md"
    if not path.exists():
        return path
    counter = 2
    while True:
        path = directory / f"{stem}_r{counter}.md"
        if not path.exists():
            return path
        counter += 1


def run_draft_pipeline(
    project_root: Path,
    state,
    prompts_dir: Optional[Path] = None,
    draft_worker: Optional[dict] = None,
    revise_worker: Optional[dict] = None,
) -> dict:
    """1단계(Gemini 초고) → 2단계(Codex 1차 퇴고)를 자동 실행.

    Returns:
        {"ep_num", "making_dir", "stages": [ {stage, model, ok, path, chars, error} ],
         "ready_for_stage3": bool, "last_path": Path|None}
    """
    draft_worker = draft_worker or DEFAULT_DRAFT_WORKER
    revise_worker = revise_worker or DEFAULT_REVISE_WORKER

    ep_num = state.episode_count + 1
    making_dir = project_root / "episodes" / f"ep{ep_num:03d}_making"
    making_dir.mkdir(parents=True, exist_ok=True)
    context = PhaseAgent.load_context(project_root, state)

    stages: list[dict] = []

    # --- Stage 1: Gemini 초고 ---
    s1 = {"stage": "1 초고", "model": draft_worker["type"], "ok": False,
          "path": None, "chars": 0, "error": None}
    try:
        gp = create_provider(draft_worker)
        err = gp.validate()
        if err:
            raise RuntimeError(err)
        wagent = WritingAgent(gp, prompts_dir=prompts_dir)
        draft = wagent.write_episode(context, instructions=DRAFT_INSTRUCTIONS)
        p1 = _versioned_path(making_dir, "01_draft_gemini")
        p1.write_text(
            _stage_header("1 초고", draft_worker["type"], ep_num, None, len(draft)) + draft + "\n",
            encoding="utf-8",
        )
        s1.update(ok=True, path=p1, chars=len(draft))
    except Exception as e:  # noqa: BLE001
        s1["error"] = str(e)
    stages.append(s1)

    if not s1["ok"]:
        return {"ep_num": ep_num, "making_dir": making_dir, "stages": stages,
                "ready_for_stage3": False, "last_path": None}

    # --- Stage 2: Codex 1차 퇴고 ---
    s2 = {"stage": "2 1차퇴고", "model": revise_worker["type"], "ok": False,
          "path": None, "chars": 0, "error": None}
    try:
        cp = create_provider(revise_worker)
        err = cp.validate()
        if err:
            raise RuntimeError(err)
        ragent = RevisionAgent(cp, prompts_dir=prompts_dir)
        draft_text = stages[0]["path"].read_text(encoding="utf-8")
        revised = ragent.copyedit(context, draft_text)
        p2 = _versioned_path(making_dir, "02_revise1_codex")
        p2.write_text(
            _stage_header("2 1차퇴고", revise_worker["type"], ep_num, stages[0]["path"].name,
                          len(revised)) + revised + "\n",
            encoding="utf-8",
        )
        s2.update(ok=True, path=p2, chars=len(revised))
    except Exception as e:  # noqa: BLE001
        s2["error"] = str(e)
    stages.append(s2)

    return {
        "ep_num": ep_num,
        "making_dir": making_dir,
        "stages": stages,
        "ready_for_stage3": s2["ok"],
        "last_path": s2["path"] if s2["ok"] else s1["path"],
    }
