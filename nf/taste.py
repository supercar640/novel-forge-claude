"""재미/취향 학습 토대 — PD 결정 신호를 누적하고 취향 프로파일을 주입.

핵심 제약: 모델 가중치는 파인튜닝할 수 없다. 따라서 "학습"은 PD 신호를 쌓아
`context/taste_profile.md`(사람이 읽고 PD가 고칠 수 있는 산출물)에 distill하고,
이를 프롬프트에 되먹이는 선호 조건화다.

이 모듈(토대)이 담당하는 것:
  - 신호 자동 로깅: select/discard/hold/revise/approve → taste/signals.jsonl
  - 프로파일 시드: 콜드 스타트용 웹소설 재미 원칙
주입은 base_agent가 context/taste_profile.md를 읽어 수행한다.
distill(reflection)은 후속 단계(taste-learn)에서 붙인다.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def signals_path(root: Path) -> Path:
    return root / "taste" / "signals.jsonl"


def profile_path(root: Path) -> Path:
    # context/ 안에 두어 base_agent의 기존 주입 경로를 탄다.
    return root / "context" / "taste_profile.md"


def prob_class(p: Optional[float]) -> str:
    """확률 → 3분류 (N>0.30 / M 0.10~0.30 / R<0.10)."""
    if p is None:
        return "?"
    if p > 0.30:
        return "N"
    if p >= 0.10:
        return "M"
    return "R"


def item_brief(item) -> dict:
    """Item → 신호용 요약 dict."""
    return {
        "id": getattr(item, "id", None),
        "text": (getattr(item, "text", "") or "")[:200],
        "prob": getattr(item, "probability", None),
        "class": prob_class(getattr(item, "probability", None)),
    }


def log_signal(root: Path, state, action: str, **fields) -> None:
    """taste/signals.jsonl에 신호 한 줄 적재. 절대 본 흐름을 깨지 않는다.

    ep/phase/step는 state에서 자동 채운다.
    """
    try:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "ep": getattr(state, "episode_count", None),
            "phase": getattr(state, "phase", None),
            "step": getattr(state, "step", None),
            "action": action,
        }
        entry.update(fields)
        sp = signals_path(root)
        sp.parent.mkdir(exist_ok=True)
        with open(sp, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # 신호가 쌓이기 시작하면 프로파일이 항상 존재하도록 보장 (기존 프로젝트 대응)
        ensure_profile(root)
    except Exception:
        # 로깅 실패가 CLI를 막아선 안 된다.
        pass


def ensure_profile(root: Path) -> bool:
    """프로파일이 없으면 시드한다. 새로 만들었으면 True."""
    p = profile_path(root)
    if p.exists():
        return False
    return seed_profile(root, force=False)


def seed_profile(root: Path, force: bool = False) -> bool:
    """context/taste_profile.md를 시드. 이미 있고 force=False면 건드리지 않음."""
    p = profile_path(root)
    if p.exists() and not force:
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_seed_text(), encoding="utf-8")
    return True


def _seed_text() -> str:
    today = datetime.now().date().isoformat()
    return f"""# PD 취향·재미 프로파일 (v0, 시드)

> 이 파일은 PD의 결정 신호(`taste/signals.jsonl`)에서 학습되어 진화합니다.
> '학습됨' 섹션은 `taste-learn`이 갱신 제안하고 PD가 승인합니다.
> 'PD 고정 지침'은 PD가 직접 적고, 학습이 덮어쓰지 않습니다.
> _마지막 갱신: {today}_

## 재미 원칙 (시드 — 웹소설 기본기)
- **사이다 우선**: 고구마(답답함)는 길게 끌지 말고 회차 내 통쾌하게 해소한다.
- **의외성 ≠ 무개연**: 놀랍되 돌이켜보면 납득되는 전개. 떡밥을 미리 깔아 둔다.
- **김빠짐 경계**: 가장 뻔한 선택은 피한다. 독자가 예측한 대로만 가면 재미가 죽는다.
- **훅과 클리프행어**: 회차 끝에 다음 화를 못 참게 만드는 한 방을 남긴다.
- **캐릭터 매력**: 주인공의 결정·대사에 개성과 통쾌함이 드러나게 한다.
- **장면의 밀도**: 인상적인 디테일(감각·대사) 하나는 요약하지 말고 살려서 쓴다.

## 회피 패턴 (학습됨)
<!-- PD가 "뻔하다"며 폐기/반려한 패턴이 누적됩니다. (아직 비어 있음) -->

## 살려야 할 재미 요소 (학습됨)
<!-- PD가 호평했거나 보존을 원한 요소가 누적됩니다. 집필·퇴고 시 보존 우선. (아직 비어 있음) -->

## 문체·톤 선호 (학습됨)
<!-- revise 피드백에서 드러난 문체 선호가 누적됩니다. (아직 비어 있음) -->

## PD 고정 지침 (수동 — 학습이 덮어쓰지 않음)
<!-- PD가 직접 못 박는 규칙을 여기 적습니다. -->
"""
