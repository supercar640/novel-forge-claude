"""Phase 2: Development Agent — 전개 옵션 생성."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base_agent import PhaseAgent
from ..providers.base import AIProvider


PROMPT_FILE = "phase2_development.md"


class DevelopmentAgent(PhaseAgent):
    """Phase 2 에이전트: 전개 옵션 생성 (3분류 확률 분포)."""

    def __init__(self, provider: AIProvider, prompts_dir: Optional[Path] = None, **kwargs):
        template = _load_template(prompts_dir)
        super().__init__(provider, template, **kwargs)

    def propose_developments(self, context: dict, *, ensemble: bool = False) -> str:
        """컨텍스트 기반 전개 옵션 생성.

        ensemble=False: 5개 (N2/M1/R2) — 단일 제안용.
        ensemble=True:  3개 (N1/M1/R1) — 모델별 분담용 (여러 모델 합산해 큐레이션).

        반환 형식 (파싱 필요):
            [N] 옵션 1. <text>...</text><probability>0.XX</probability>
            ...
        """
        if ensemble:
            user_msg = (
                "현재 컨텍스트를 바탕으로 다음 회차의 전개 옵션 3개를 제안해 주세요.\n\n"
                "## 확률 분포 규칙 (각 분류 1개씩, 총 3개)\n"
                "- [N]ormal 1개: probability > 0.30 (자연스러운 전개)\n"
                "- [M]oderate 1개: probability 0.10~0.30 (약간 의외)\n"
                "- [R]are 1개: probability < 0.10 (독창적, 맥락 부합 필수)\n\n"
                "## 출력 형식\n"
                "[N/M/R] 옵션 N.\n"
                "<text>방향성 요약</text>\n"
                "<probability>0.XX</probability>\n"
            )
        else:
            user_msg = (
                "현재 컨텍스트를 바탕으로 다음 회차의 전개 옵션 5개를 제안해 주세요.\n\n"
                "## 확률 분포 규칙\n"
                "- [N]ormal 2개: probability > 0.30 (자연스러운 전개)\n"
                "- [M]oderate 1개: probability 0.10~0.30 (약간 의외)\n"
                "- [R]are 2개: probability < 0.10 (독창적, 맥락 부합 필수)\n\n"
                "## 출력 형식\n"
                "[N/M/R] 옵션 N.\n"
                "<text>방향성 요약</text>\n"
                "<probability>0.XX</probability>\n"
            )
        response = self.execute(context, user_msg)
        return response.content


def _load_template(prompts_dir: Optional[Path] = None) -> str:
    if prompts_dir:
        path = prompts_dir / PROMPT_FILE
        if path.exists():
            return path.read_text(encoding="utf-8")
    default_path = Path(__file__).parent.parent / "prompts" / PROMPT_FILE
    if default_path.exists():
        return default_path.read_text(encoding="utf-8")
    return _DEFAULT_TEMPLATE


_DEFAULT_TEMPLATE = """\
당신은 웹소설 전개 기획 전문 AI 어시스턴트입니다.
기존 컨텍스트(캐릭터, 세계관, 플롯, 복선)를 깊이 이해하고,
다음 회차의 전개 옵션을 제안합니다.

## 역할
- 이전 에피소드의 흐름을 이어받되, 다양한 가능성을 제시합니다.
- 3분류 확률 분포(Normal/Moderate/Rare)를 엄격히 준수합니다.
- 각 옵션은 독립적이면서도 맥락에 부합해야 합니다.
- 복선(foreshadow.md)의 회수 기회를 적극 활용합니다.

## 출력 규칙
- 한국어로 출력합니다.
- 반드시 <text>와 <probability> 태그를 사용합니다.
"""
