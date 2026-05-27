"""Phase 3: Writing Agent — 에피소드/장면 집필."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base_agent import PhaseAgent
from ..providers.base import AIProvider


PROMPT_FILE = "phase3_writing.md"


class WritingAgent(PhaseAgent):
    """Phase 3 에이전트: 집필 (에피소드/장면/자동 모드)."""

    def __init__(self, provider: AIProvider, prompts_dir: Optional[Path] = None, **kwargs):
        template = _load_template(prompts_dir)
        # 집필은 대량 출력이므로 max_tokens 기본값 높게
        kwargs.setdefault("max_tokens", 8192)
        kwargs.setdefault("temperature", 0.8)
        super().__init__(provider, template, **kwargs)

    def write_episode(self, context: dict, instructions: str = "") -> str:
        """에피소드 1회분 집필 (5,500자+)."""
        user_msg = (
            "선정된 전개 방향을 바탕으로 에피소드 1회분을 집필해 주세요.\n\n"
            "## 요구사항\n"
            "- 최소 5,500자 이상의 본문\n"
            "- 문체 참조를 반영한 서술\n"
            "- 복선을 자연스럽게 매설하거나 회수\n"
            "- 장면 전환은 `---`로 구분\n"
        )
        if instructions:
            user_msg += f"\n## 추가 지시\n{instructions}\n"
        response = self.execute(context, user_msg)
        return response.content

    def relay_pass(
        self,
        context,
        role_title,
        role_instructions,
        prior_text=None,
        *,
        temperature=None,
        min_chars=None,
    ):
        """작가실 릴레이의 한 단계를 수행. 역할 지시에 따라 원고를 생성/발전시킨다.

        min_chars가 None이면 분량을 강제하지 않는다.
        (5,500자 게이트는 webnovel 모드 한정 — run_draft_room이 분기해 전달한다.)
        """
        user_msg = f"## 당신의 역할: {role_title}\n{role_instructions}\n\n"
        if prior_text:
            user_msg += f"## 직전 단계 산출물 (이어받아 발전시킬 원고)\n{prior_text}\n\n"
        user_msg += "위 역할에 충실하게, 에피소드 1회분 원고를 출력하세요.\n"
        if min_chars:
            user_msg += f"- 최소 {min_chars:,}자 이상의 본문\n"
        user_msg += (
            "- 장면 전환은 `---`로 구분\n"
            "- 설명·메타코멘트·역할 언급 없이 본문만 출력\n"
        )
        response = self.execute(context, user_msg, temperature=temperature)
        return response.content

    def write_scene(self, context: dict, scene_num: int, instructions: str = "") -> str:
        """장면 1개 집필 (scene 모드)."""
        user_msg = (
            f"장면 {scene_num}을 집필해 주세요.\n\n"
            "## 요구사항\n"
            "- 하나의 연속된 장면으로 작성\n"
            "- 문체 참조를 반영한 서술\n"
        )
        if instructions:
            user_msg += f"\n## 추가 지시\n{instructions}\n"
        response = self.execute(context, user_msg)
        return response.content

    def revise_draft(self, context: dict, draft: str, feedback: str) -> str:
        """PD 피드백 기반 원고 수정."""
        user_msg = (
            f"## 현재 원고\n{draft}\n\n"
            f"## PD 피드백\n{feedback}\n\n"
            "위 피드백을 반영하여 원고를 수정해 주세요.\n"
            "수정된 전체 원고를 출력해 주세요."
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
당신은 웹소설 전문 작가 AI입니다.
PD가 선정한 전개 방향과 문체를 따르며, 몰입감 높은 에피소드를 집필합니다.

## 역할
- 컨텍스트(캐릭터, 세계관, 플롯)에 충실한 서사를 전개합니다.
- 지정된 문체 참조를 최대한 반영합니다.
- 복선을 자연스럽게 매설하거나 기존 복선을 회수합니다.
- 에피소드는 최소 5,500자 이상이어야 합니다.

## 출력 규칙
- 한국어로 출력합니다.
- 장면 전환은 `---`로 구분합니다.
- 대화문과 서술을 적절히 배합합니다.
"""
