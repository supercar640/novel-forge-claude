"""전개 옵션의 뻔함을 PD 취향 프로파일 기준으로 심사하는 보조 모듈."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import create_provider
from .taste import profile_path


DEFAULT_WORKER: dict = {"type": "codex-cli", "model": "", "timeout": 300}

GUARD_SYSTEM: str = """당신은 한국 웹소설 전개안 뻔함 심사관이다.

입력으로 (a) PD 취향·재미 프로파일(재미 원칙과 회피 패턴), (b) 번호 매긴 전개 옵션 목록을 받는다.
각 옵션을 다음 기준으로 1~5점 채점한다.
- 의외성: 5점은 신선하고 예측을 벗어난다.
- 개연성: 5점은 인물, 장르, 상황 논리에 탄탄하게 맞는다.
- 매력: 5점은 다음 화를 읽고 싶게 끈다.
- 뻔함: 5점은 매우 뻔하고 예측 가능하다.

PD 취향·재미 프로파일의 회피 패턴에 해당하는 옵션은 뻔함 점수를 높게 준다.
유능하지만 예측 가능한 안전한 옵션만 있으면 가차없이 지적한다.

출력은 JSON 객체 하나만 작성한다. 코드펜스, 설명, 주석은 절대 쓰지 않는다.
형식:
{"options":[{"id":<int>,"의외성":<1-5>,"개연성":<1-5>,"매력":<1-5>,"뻔함":<1-5>,"평":"<한 줄>"}],"all_too_safe":<bool>,"verdict":"<전체 평 한두 줄>","suggestion":"<재생성/보완 제안>"}

all_too_safe는 신선하고 매력적인 선택지가 사실상 없을 때 true로 둔다."""


def build_user_message(profile: str, items: list[dict]) -> str:
    """PD 취향 프로파일과 전개 옵션 목록을 심사용 프롬프트로 조립한다."""
    lines = [
        "=== PD 취향·재미 프로파일 ===",
        profile,
        "=== 전개 옵션 ===",
    ]
    for item in items:
        item_id = item.get("id")
        text = item.get("text", "")
        prob = item.get("prob")
        item_class = item.get("class", "?")
        lines.append(f"[{item_class}] {item_id}. {text} (prob={prob})")
    return "\n".join(lines)


def parse_guard_json(text: str) -> dict | None:
    """모델 응답에서 JSON 객체만 추출해 파싱한다."""
    cleaned = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or start > end:
        return None

    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def is_all_too_safe(parsed: dict | None) -> bool:
    """파싱 결과에서 안전한 선택지만 있는지 판단한다."""
    if not parsed:
        return False

    all_too_safe = parsed.get("all_too_safe")
    if isinstance(all_too_safe, bool):
        return all_too_safe

    options = parsed.get("options")
    if not isinstance(options, list):
        return True

    for option in options:
        if not isinstance(option, dict):
            continue
        surprise = option.get("의외성")
        appeal = option.get("매력")
        cliche = option.get("뻔함")
        if isinstance(surprise, (int, float)) and surprise >= 4:
            return False
        if (
            isinstance(appeal, (int, float))
            and isinstance(cliche, (int, float))
            and appeal >= 4
            and cliche <= 2
        ):
            return False
    return True


def run_cliche_guard(
    root: Path,
    items: list[dict],
    worker: dict | None = None,
    *,
    max_tokens: int = 2000,
) -> dict:
    """전개 옵션 목록을 워커 모델로 평가하고 파싱 결과와 원문을 반환한다."""
    if not items:
        return {"ok": False, "reason": "평가할 전개안이 없습니다"}

    try:
        profile_file = profile_path(root)
        profile = profile_file.read_text(encoding="utf-8") if profile_file.exists() else ""

        worker_config = worker or DEFAULT_WORKER
        provider = create_provider(worker_config)
        err = provider.validate()
        if err:
            return {"ok": False, "reason": err}

        content = provider.generate(
            GUARD_SYSTEM,
            build_user_message(profile, items),
            max_tokens=max_tokens,
        ).content
        parsed = parse_guard_json(content)

        return {
            "ok": True,
            "parsed": parsed,
            "raw": content,
            "too_safe": is_all_too_safe(parsed),
            "worker": worker_config["type"],
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)}
