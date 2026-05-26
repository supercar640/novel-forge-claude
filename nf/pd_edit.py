"""PD 직접 편집본에서 삭제 및 추가된 줄을 요약하는 유틸리티입니다."""
from __future__ import annotations

import difflib
import re
from typing import TypeAlias


EditSummary: TypeAlias = dict[str, list[str] | int]


def _strip_meta(text: str) -> str:
    """맨 앞 HTML 메타 주석 블록을 제거합니다."""
    return re.sub(r"^\s*<!--.*?-->\s*", "", text, count=1, flags=re.DOTALL).strip()


def _trim_item(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def summarize_edit(
    before: str,
    after: str,
    *,
    max_items: int = 20,
    max_len: int = 200,
) -> EditSummary:
    """AI 초안과 PD 퇴고본을 비교해 빠진 줄과 추가된 줄을 요약합니다."""
    before_clean = _strip_meta(before)
    after_clean = _strip_meta(after)
    before_lines = [line.strip() for line in before_clean.splitlines() if line.strip()]
    after_lines = [line.strip() for line in after_clean.splitlines() if line.strip()]

    removed: list[str] = []
    added: list[str] = []

    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"delete", "replace"}:
            removed.extend(before_lines[i1:i2])
        if tag in {"insert", "replace"}:
            added.extend(after_lines[j1:j2])

    removed_count = len(removed)
    added_count = len(added)

    return {
        "removed": [_trim_item(item, max_len) for item in removed[:max_items]],
        "added": [_trim_item(item, max_len) for item in added[:max_items]],
        "removed_count": removed_count,
        "added_count": added_count,
    }
