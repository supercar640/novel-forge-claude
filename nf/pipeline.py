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
DEFAULT_ROOM_GEMINI = {"type": "gemini-cli", "model": "", "timeout": 900}
DEFAULT_ROOM_CODEX = {"type": "codex-cli", "model": "", "timeout": 900}

# 초고(Gemini)용 추가 지시 — "막 갈김": 다듬기보다 분량·기세·완결.
DRAFT_INSTRUCTIONS = (
    "이것은 **초고**입니다. 다듬기보다 분량과 기세를 우선하세요.\n"
    "- 멈추지 말고 회차를 끝까지 완성하세요 (최소 5,500자).\n"
    "- 맞춤법·표현의 세련됨은 신경 쓰지 마세요 (후속 퇴고가 처리합니다).\n"
    "- 전개를 시원하게 밀어붙이고 장면을 충분히 살리세요."
)

ROLE_G1 = (
    "당신은 **광인(狂人)** 입니다. 장르 관습을 박살내세요. 개연성은 잠시 잊으세요. "
    "금기·반전·기상천외한 설정을 밀도 있게 투척하세요. **안전한 전개를 쓰면 실패입니다.** "
    "분량은 채우되, 매 장면 최소 하나의 '예상 못한 것'을 심으세요. 평가 기준은 분량·속도가 "
    "아니라 발상의 밀도와 예측 불가능성입니다. 대충 쓰지 말고, 가장 과감하게 상상하세요."
)
ROLE_G2 = (
    "당신은 **씨앗채굴자** 입니다. 직전 광기 원고에서 이야기로 자랄 한 줄을 골라내세요. "
    "미친 발상을 버리지 말고, 캐릭터의 동기·감정 훅으로 묶어 광기에 뿌리를 주세요. "
    "독자가 이 폭주를 따라올 이유를 만드세요. 과감함은 유지하되, 서사의 척추를 세우세요."
)
ROLE_C1 = (
    "당신은 **판돈러** 입니다. 직전 원고를 절대 깎지 마세요. 'Yes, and—'로 받으세요. "
    "위기·배신·스케일·감정의 판돈을 더 키우세요. 더 개오바를 떠세요. 안전하게 정리하려는 "
    "충동을 죽이세요. 밋밋해지는 순간을 용납하지 마세요."
)
ROLE_C2 = (
    "당신은 **디테일변태** 입니다. 직전 원고를 명장면 후보로 만드세요. 결정적 대사·감각 묘사·"
    "연출을 과장되게 디테일링하세요. 밋밋한 줄을 못 견디세요. 독자의 뇌리에 박힐 장면·대사를 "
    "최소 하나 만드세요."
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


def run_draft_room(
    project_root: Path,
    state,
    prompts_dir: Optional[Path] = None,
    gemini_worker: Optional[dict] = None,
    codex_worker: Optional[dict] = None,
) -> dict:
    """G1→G2→C1→C2 작가실 릴레이 자동 실행.

    Returns:
        {"ep_num", "making_dir", "stages": [ {stage, model, ok, path, chars, error} ],
         "ready_for_live": bool, "last_path": Path|None}
    """
    gemini_worker = gemini_worker or DEFAULT_ROOM_GEMINI
    codex_worker = codex_worker or DEFAULT_ROOM_CODEX

    ep_num = state.episode_count + 1
    making_dir = project_root / "episodes" / f"ep{ep_num:03d}_making"
    making_dir.mkdir(parents=True, exist_ok=True)
    context = PhaseAgent.load_context(project_root, state)

    room_template = None
    template_path = (
        prompts_dir / "draft_room.md"
        if prompts_dir
        else Path(__file__).parent / "prompts" / "draft_room.md"
    )
    if template_path.exists():
        room_template = template_path.read_text(encoding="utf-8")

    stage_defs = [
        ("G1 광인", ROLE_G1, gemini_worker, 1.0, "01_g1_chaos"),
        ("G2 씨앗채굴자", ROLE_G2, gemini_worker, 0.8, "02_g2_seed"),
        ("C1 판돈러", ROLE_C1, codex_worker, 0.9, "03_c1_stakes"),
        ("C2 디테일변태", ROLE_C2, codex_worker, 0.9, "04_c2_detail"),
    ]

    stages: list[dict] = []
    prior = None
    previous_path = None
    last_path = None

    for role_title, instructions, worker, temp, stem in stage_defs:
        stage = {
            "stage": role_title,
            "model": worker["type"],
            "ok": False,
            "path": None,
            "chars": 0,
            "error": None,
        }
        try:
            provider = create_provider(worker)
            err = provider.validate()
            if err:
                raise RuntimeError(err)
            agent = WritingAgent(provider, prompts_dir=prompts_dir)
            if room_template:
                agent.prompt_template = room_template
            text = agent.relay_pass(
                context,
                role_title,
                instructions,
                prior_text=prior,
                temperature=temp,
            )
            path = _versioned_path(making_dir, stem)
            path.write_text(
                _stage_header(
                    role_title,
                    worker["type"],
                    ep_num,
                    previous_path.name if previous_path else None,
                    len(text),
                )
                + text
                + "\n",
                encoding="utf-8",
            )
            stage.update(ok=True, path=path, chars=len(text))
            prior = text
            previous_path = path
            last_path = path
        except Exception as e:  # noqa: BLE001
            stage["error"] = str(e)
            stages.append(stage)
            break
        stages.append(stage)

    return {
        "ep_num": ep_num,
        "making_dir": making_dir,
        "stages": stages,
        "ready_for_live": all(s["ok"] for s in stages) and len(stages) == 4,
        "last_path": last_path,
    }
