"""PD 선택 신호를 요약하고 taste_profile 갱신 제안을 생성하는 학습 도구."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import create_provider
from .taste import profile_path, signals_path


DEFAULT_WORKER: dict[str, Any] = {"type": "gemini-cli", "model": "", "timeout": 600}


REFLECTION_SYSTEM: str = """당신은 한국 웹소설 집필 도구의 PD 취향 분석가입니다.

입력으로 (a) 현재 taste_profile.md 전문, (b) PD 선택/폐기/수정 신호 다이제스트를 받습니다.
당신의 임무는 근거가 있는 학습 결과만 반영하여 갱신된 taste_profile.md 전문을 출력하는 것입니다.

엄격 규칙:
- 문서 구조와 헤더는 그대로 유지합니다.
- 반드시 다음 헤더를 유지합니다: `## 재미 원칙`, `## 회피 패턴 (학습됨)`, `## 살려야 할 재미 요소 (학습됨)`, `## 문체·톤 선호 (학습됨)`, `## PD 고정 지침 (수동 — 학습이 덮어쓰지 않음)`.
- `## PD 고정 지침 (수동 — 학습이 덮어쓰지 않음)` 섹션의 내용은 한 글자도 바꾸지 말고 그대로 보존합니다.
- '학습됨' 3개 섹션은 신호 다이제스트의 근거에 기반해 다시 작성합니다. 증거가 없으면 비워둡니다. 추측하지 않습니다.
- `## 재미 원칙`의 시드 원칙은 삭제하지 말고, PD 특유의 정제만 덧붙입니다.
- 맨 위 버전 라인(`# PD 취향·재미 프로파일 (vN ...)`)의 버전을 올리고 날짜를 오늘 날짜로 갱신합니다.
- 출력은 마크다운 본문만 작성합니다. 설명, 코멘트, 코드펜스는 절대 출력하지 않습니다.
"""


def summarize_signals(signals: list[dict]) -> str:
    """신호 목록을 사람이 읽는 한국어 다이제스트로 요약합니다."""
    action_counts: dict[str, int] = {}
    chosen_classes: dict[str, int] = {}
    rejected_classes: dict[str, int] = {}
    discard_texts: list[str] = []
    revise_feedbacks: list[str] = []

    for signal in signals:
        action = str(signal.get("action") or "?")
        action_counts[action] = action_counts.get(action, 0) + 1

        if action == "select":
            for item in _as_list(signal.get("chosen")):
                cls = _class_of(item)
                chosen_classes[cls] = chosen_classes.get(cls, 0) + 1
            for item in _as_list(signal.get("rejected")):
                cls = _class_of(item)
                rejected_classes[cls] = rejected_classes.get(cls, 0) + 1

        if action == "discard":
            item = signal.get("item")
            if isinstance(item, dict):
                text = _clean_text(item.get("text"))
                if text:
                    discard_texts.append(text)

        if action == "revise":
            feedback = _clean_text(signal.get("feedback"))
            if feedback:
                revise_feedbacks.append(feedback)

    dominant = _dominant_class(chosen_classes)
    lines = [
        "## 신호 요약",
        f"- 총 신호 수: {len(signals)}",
        f"- action별 건수: {_format_counts(action_counts)}",
        "",
        "## select 경향",
        f"- chosen class 분포: {_format_counts(chosen_classes)}",
        f"- rejected class 분포: {_format_counts(rejected_classes)}",
        f"- 선택된 것의 평균 class 성향: {dominant}",
        "",
        "## discard된 item.text 목록",
    ]

    if discard_texts:
        for text, count in _top_texts(discard_texts, limit=30):
            suffix = f" ({count}회)" if count > 1 else ""
            lines.append(f"- {text}{suffix}")
    else:
        lines.append("- 없음")

    lines.extend(["", "## revise feedback 목록"])
    if revise_feedbacks:
        for feedback in revise_feedbacks[:30]:
            lines.append(f"- {feedback}")
    else:
        lines.append("- 없음")

    return "\n".join(lines)


def run_taste_learn(root: Path, worker: dict | None = None, *, max_tokens: int = 6000) -> dict:
    """signals.jsonl을 반영한 taste_profile 갱신 제안을 생성합니다."""
    try:
        worker_config = dict(worker or DEFAULT_WORKER)
        current_profile_path = profile_path(root)
        current_profile = ""
        if current_profile_path.exists():
            current_profile = current_profile_path.read_text(encoding="utf-8")

        signals = _read_signals(signals_path(root))
        if not signals:
            return {"ok": False, "reason": "신호 없음"}

        provider = create_provider(worker_config)
        error = provider.validate()
        if error:
            return {"ok": False, "reason": error}

        digest = summarize_signals(signals)
        user_message = "\n".join(
            [
                "=== 현재 taste_profile.md ===",
                current_profile,
                "",
                "=== 신호 다이제스트 ===",
                digest,
            ]
        )
        response = provider.generate(
            REFLECTION_SYSTEM,
            user_message,
            max_tokens=max_tokens,
        )

        proposal_path = root / "taste" / "profile_proposal.md"
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(response.content, encoding="utf-8")

        return {
            "ok": True,
            "proposal_path": proposal_path,
            "signal_count": len(signals),
            "digest": digest,
            "worker": worker_config["type"],
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


def apply_proposal(root: Path) -> dict:
    """학습 제안 파일을 실제 taste_profile.md에 적용합니다."""
    proposal_path = root / "taste" / "profile_proposal.md"
    if not proposal_path.exists():
        return {"ok": False, "reason": "제안 파일 없음"}

    current_profile_path = profile_path(root)
    backup_path: Path | None = None
    if current_profile_path.exists():
        backup_dir = root / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = _next_backup_path(backup_dir)
        backup_path.write_text(current_profile_path.read_text(encoding="utf-8"), encoding="utf-8")

    current_profile_path.parent.mkdir(parents=True, exist_ok=True)
    current_profile_path.write_text(proposal_path.read_text(encoding="utf-8"), encoding="utf-8")
    return {"ok": True, "backup": backup_path, "applied": current_profile_path}


def _read_signals(path: Path) -> list[dict]:
    signals: list[dict] = []
    if not path.exists():
        return signals

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            signals.append(data)
    return signals


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _class_of(item: Any) -> str:
    if not isinstance(item, dict):
        return "?"
    cls = item.get("class")
    if cls in {"N", "M", "R", "?"}:
        return str(cls)
    return "?"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "없음"
    ordered_keys = ["select", "discard", "hold", "revise", "hold_draft", "N", "M", "R", "?"]
    keys = [key for key in ordered_keys if key in counts]
    keys.extend(sorted(key for key in counts if key not in ordered_keys))
    return ", ".join(f"{key} {counts[key]}건" for key in keys)


def _dominant_class(counts: dict[str, int]) -> str:
    meaningful = {key: counts.get(key, 0) for key in ("N", "M", "R")}
    total = sum(meaningful.values())
    if total == 0:
        return "판단 불가"

    top_count = max(meaningful.values())
    top_classes = [key for key, count in meaningful.items() if count == top_count and count > 0]
    if len(top_classes) == 1:
        return f"{top_classes[0]} 성향"
    return "/".join(top_classes) + " 혼합 성향"


def _top_texts(texts: list[str], *, limit: int) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for index, text in enumerate(texts):
        counts[text] = counts.get(text, 0) + 1
        first_seen.setdefault(text, index)

    return sorted(counts.items(), key=lambda item: (-item[1], first_seen[item[0]]))[:limit]


def _next_backup_path(backup_dir: Path) -> Path:
    index = 1
    while True:
        candidate = backup_dir / f"taste_profile_v{index}.md"
        if not candidate.exists():
            return candidate
        index += 1
