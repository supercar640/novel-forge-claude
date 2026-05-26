"""Phase 4: Revision Agent — 퇴고, 교정/교열, 컨텍스트 갱신 제안."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base_agent import PhaseAgent
from ..providers.base import AIProvider


PROMPT_FILE = "phase4_revision.md"


class RevisionAgent(PhaseAgent):
    """Phase 4 에이전트: 퇴고 및 컨텍스트 갱신."""

    def __init__(self, provider: AIProvider, prompts_dir: Optional[Path] = None, **kwargs):
        template = _load_template(prompts_dir)
        kwargs.setdefault("temperature", 0.3)
        super().__init__(provider, template, **kwargs)

    def proofread(self, context: dict, manuscript: str) -> str:
        """원고 퇴고 (문체, 오탈자, 설정 충돌 검토)."""
        user_msg = (
            f"## 원고\n{manuscript}\n\n"
            "위 원고를 퇴고해 주세요.\n\n"
            "## 검토 항목\n"
            "- 문체 일관성 (문체 참조 및 가이드라인 기준)\n"
            "- 오탈자, 맞춤법, 비문\n"
            "- 설정 충돌 (캐릭터 프로필, 세계관과의 불일치)\n"
            "- 복선 정합성 (foreshadow.md와 대조)\n\n"
            "수정된 전체 원고를 출력해 주세요."
        )
        response = self.execute(context, user_msg)
        return response.content

    def copyedit(self, context: dict, manuscript: str) -> str:
        """1차 퇴고 (라인 레벨): 맞춤법·오탈자·비문, 문장 다듬기, 설정 표기 오류.

        서사 구조/전개는 바꾸지 않고 원형을 유지한다. 컨텍스트 차원의 정합성
        검수는 후속 2차 퇴고(별도)에서 다룬다.
        """
        user_msg = (
            f"## 원고 (초고)\n{manuscript}\n\n"
            "위 초고를 **1차 퇴고**해 주세요. 라인 레벨 교정에 집중합니다.\n\n"
            "## 검토 항목\n"
            "- 맞춤법, 오탈자, 띄어쓰기\n"
            "- 비문, 어색한 문장 다듬기 (가독성)\n"
            "- 명백한 설정 표기 오류 (인명·지명·호칭의 표기 불일치)\n\n"
            "## 제약\n"
            "- 서사 구조와 전개는 바꾸지 마세요 (원형 유지).\n"
            "- 새로운 사건·설정을 추가하지 마세요.\n"
            "- 수정된 전체 원고를 그대로 출력하세요 (설명·코멘트 없이 본문만).\n"
        )
        response = self.execute(context, user_msg)
        return response.content

    def suggest_context_updates(self, context: dict, manuscript: str) -> str:
        """에피소드 완성 후 컨텍스트 갱신 제안."""
        user_msg = (
            f"## 이번 회차 완성 원고\n{manuscript[:10000]}\n\n"
            "이번 회차에서 변경/추가된 내용을 바탕으로 "
            "컨텍스트 파일 갱신 사항을 제안해 주세요.\n\n"
            "## 갱신 대상 파일\n"
            "- character_profiles.md: 캐릭터 변화, 새 캐릭터\n"
            "- setting_world.md: 새로운 장소, 설정 변경\n"
            "- plot_outline.md: 플롯 진행 업데이트\n"
            "- themes.md / tone.md: 필요 시\n"
            "- foreshadow.md: 새 복선 추가, 회수된 복선 표시\n"
            "- payoff.md: 이번 회차에서 회수된 복선 기록\n\n"
            "파일별로 구분하여 구체적인 갱신 내용을 출력해 주세요."
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
당신은 웹소설 편집/교정 전문 AI입니다.
원고의 품질을 높이고, 설정 충돌을 잡아내며, 컨텍스트를 정리합니다.

## 역할
- 문체, 오탈자, 맞춤법, 비문을 교정합니다.
- 캐릭터/세계관 설정과의 충돌을 찾아냅니다.
- 복선의 정합성을 검토합니다.
- 컨텍스트 파일 갱신 사항을 제안합니다.

## 출력 규칙
- 한국어로 출력합니다.
- 교정 시 수정된 전체 원고를 출력합니다.
- 갱신 제안 시 파일별로 구분하여 구체적으로 제안합니다.
"""
