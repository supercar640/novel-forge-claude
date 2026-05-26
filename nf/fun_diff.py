"""웹소설 퇴고 전후의 재미 손실을 검수하는 도우미 모듈입니다."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import create_provider
from .taste import profile_path


DEFAULT_WORKER: dict = {"type": "codex-cli", "model": "", "timeout": 600}

FUN_DIFF_SYSTEM: str = """당신은 웹소설 "재미 보존 검수관"입니다.

입력으로 (a) PD 취향·재미 프로파일(살려야 할 재미 요소 + 재미 원칙), (b) BEFORE 원고(초고/직전), (c) AFTER 원고(퇴고본)를 받습니다.

당신의 임무는 BEFORE에 있던 재미 요소가 AFTER에서 삭제되거나 약화된 지점을 찾아내는 것입니다. 특히 인상적 대사, 장면의 힘, 반전, 감각 묘사, 위트, 캐릭터 개성, 문장의 목소리가 밋밋해졌는지 검수하세요.

단순 교정으로 정당화되는 변경은 지적하지 마세요. 오탈자, 맞춤법, 비문 수정, 명백한 문장 정리 자체는 문제가 아닙니다. 재미·개성·목소리의 실제 손실만 지적하세요.

출력은 JSON 객체 하나만 내세요. 코드펜스, 설명, 주석은 절대 붙이지 마세요.

형식:
{"regressions":[{"요소":"<무엇>","before":"<원문 근거 짧게>","after":"<바뀐 양상>","심각도":<1-5>,"복원제안":"<어떻게 살릴지>"}],"fun_regressed":<bool>,"verdict":"<총평 한두 줄>","preserved_well":["<잘 보존된 재미 요소>"]}

fun_regressed는 재미를 실제로 깎은 손실이 하나라도 있으면 true로 설정하세요."""


def build_user_message(profile: str, before: str, after: str) -> str:
    return (
        "=== PD 취향·재미 프로파일 ===\n"
        f"{profile}\n"
        "=== BEFORE (초고/직전) ===\n"
        f"{before}\n"
        "=== AFTER (퇴고본) ===\n"
        f"{after}"
    )


def _strip_meta(text: str) -> str:
    return re.sub(r"^\s*<!--.*?-->\s*", "", text, count=1, flags=re.DOTALL).strip()


def parse_fun_json(text: str) -> dict | None:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.IGNORECASE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        return None

    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def fun_regressed_flag(parsed: dict | None) -> bool:
    if not parsed:
        return False

    fun_regressed = parsed.get("fun_regressed")
    if isinstance(fun_regressed, bool):
        return fun_regressed

    regressions = parsed.get("regressions")
    if not isinstance(regressions, list):
        return False

    for regression in regressions:
        if not isinstance(regression, dict):
            continue
        severity: Any = regression.get("심각도")
        if isinstance(severity, (int, float)) and severity >= 3:
            return True
    return False


def run_fun_diff(
    root: Path,
    before_path: Path,
    after_path: Path,
    worker: dict | None = None,
    *,
    max_tokens: int = 3000,
) -> dict:
    try:
        if not before_path.exists():
            return {"ok": False, "reason": f"파일 없음: {before_path}"}
        if not after_path.exists():
            return {"ok": False, "reason": f"파일 없음: {after_path}"}

        before = _strip_meta(before_path.read_text(encoding="utf-8"))
        after = _strip_meta(after_path.read_text(encoding="utf-8"))

        taste_file = profile_path(root)
        profile = taste_file.read_text(encoding="utf-8") if taste_file.exists() else ""

        worker_config = worker or DEFAULT_WORKER
        provider = create_provider(worker_config)
        err = provider.validate()
        if err:
            return {"ok": False, "reason": err}

        content = provider.generate(
            FUN_DIFF_SYSTEM,
            build_user_message(profile, before, after),
            max_tokens=max_tokens,
        ).content
        parsed = parse_fun_json(content)

        return {
            "ok": True,
            "parsed": parsed,
            "raw": content,
            "regressed": fun_regressed_flag(parsed),
            "worker": worker_config["type"],
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)}
