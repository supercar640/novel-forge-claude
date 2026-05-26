"""Phase 2 ensemble — 전개안 제안을 여러 CLI worker에 병렬 fan-out.

하이브리드 모드: NF가 외부 worker(gemini, codex 등)를 병렬 실행해 전개안 후보를
drafts/에 부어놓는다. 자기 배치 생성과 최종 큐레이션은 라이브 Claude Code 세션이
PD와 함께 수행한다 (자동 병합 없음).
"""

from __future__ import annotations

import concurrent.futures
import re
from pathlib import Path
from typing import Optional

from .agents.base_agent import PhaseAgent
from .agents.development_agent import DevelopmentAgent
from .config import create_provider

# 하이브리드 기본 외부 worker (Claude Code 자신이 세 번째 worker 역할).
DEFAULT_WORKERS = [
    {"type": "gemini-cli", "model": ""},
    {"type": "codex-cli", "model": ""},
]

_OPTION_RE = re.compile(
    r"<text>(.*?)</text>\s*<probability>\s*([0-9.]+)\s*</probability>",
    re.DOTALL,
)


def count_options(text: str) -> int:
    """<text>/<probability> 쌍의 개수를 센다."""
    return len(_OPTION_RE.findall(text or ""))


def _safe_name(worker_type: str) -> str:
    return worker_type.replace("-", "_").replace("/", "_")


def run_ensemble_developments(
    project_root: Path,
    state,
    workers: Optional[list[dict]] = None,
    prompts_dir: Optional[Path] = None,
) -> list[dict]:
    """각 worker의 DevelopmentAgent를 병렬 실행하고 결과를 drafts/에 기록.

    Returns:
        worker 순서를 보존한 결과 dict 목록.
        각 항목: {"type", "ok", "path", "options", "chars", "error"}
    """
    workers = workers or DEFAULT_WORKERS
    context = PhaseAgent.load_context(project_root, state)
    drafts_dir = project_root / "drafts"
    drafts_dir.mkdir(exist_ok=True)

    def _run_one(idx: int, wcfg: dict) -> dict:
        wtype = wcfg.get("type", "?")
        try:
            provider = create_provider(wcfg)
        except Exception as e:  # noqa: BLE001
            return {"idx": idx, "type": wtype, "ok": False, "error": f"provider 생성 실패: {e}"}
        err = provider.validate()
        if err:
            return {"idx": idx, "type": wtype, "ok": False, "error": err}
        agent = DevelopmentAgent(provider, prompts_dir=prompts_dir)
        try:
            content = agent.propose_developments(context, ensemble=True)
        except Exception as e:  # noqa: BLE001
            return {"idx": idx, "type": wtype, "ok": False, "error": str(e)}
        return {"idx": idx, "type": wtype, "ok": True, "content": content}

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(workers))) as ex:
        futs = [ex.submit(_run_one, i, w) for i, w in enumerate(workers)]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())

    results.sort(key=lambda r: r["idx"])

    for r in results:
        if r.get("ok"):
            content = r.pop("content")
            path = drafts_dir / f"ensemble_dev_{_safe_name(r['type'])}.md"
            header = f"# 전개안 후보 (worker: {r['type']})\n\n"
            path.write_text(header + content + "\n", encoding="utf-8")
            r["path"] = path
            r["options"] = count_options(content)
            r["chars"] = len(content)
        else:
            r["path"] = None
            r["options"] = 0
            r["chars"] = 0
    return results
