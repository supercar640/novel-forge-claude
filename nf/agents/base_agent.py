"""Base agent class — context injection + AI call + response parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..providers.base import AIProvider, AIResponse


class PhaseAgent:
    """Each Phase's AI work is handled by a PhaseAgent.

    The agent reads context files, builds a system prompt from
    the prompt template, then calls the AI provider.
    """

    def __init__(
        self,
        provider: AIProvider,
        prompt_template: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.provider = provider
        self.prompt_template = prompt_template
        self.temperature = temperature
        self.max_tokens = max_tokens

    def execute(
        self,
        context: dict,
        user_input: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """Build system prompt from context + template, call provider."""
        system_prompt = self._build_system_prompt(context)
        return self.provider.generate(
            system_prompt=system_prompt,
            user_message=user_input,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )

    def _build_system_prompt(self, context: dict) -> str:
        """Compose the full system prompt from template + context files.

        context dict keys:
            - "context_files": dict of {filename: content} from context/
            - "episodes": list of recent episode summaries
            - "foreshadow": content of foreshadow.md
            - "payoff": content of payoff.md
            - "selected_development": currently selected development text
            - "style_reference": style reference string
            - "episode_count": number of completed episodes
            - "revision_feedback": any PD feedback
            - "guideline": polishing guideline content
        """
        parts = [self.prompt_template]

        # PD 취향·재미 지침 (강조 주입 — 일반 컨텍스트보다 앞에 둔다)
        taste = context.get("taste_profile", "")
        if taste:
            parts.append(
                "\n\n## PD 취향·재미 지침 (생성·선정·퇴고 시 반드시 반영)\n"
                + taste
                + "\n"
            )

        # Inject context files
        context_files = context.get("context_files", {})
        if context_files:
            parts.append("\n\n## 작품 컨텍스트\n")
            for filename, content in context_files.items():
                parts.append(f"### {filename}\n{content}\n")

        # Foreshadow / payoff
        foreshadow = context.get("foreshadow", "")
        if foreshadow:
            parts.append(f"\n### 복선 (foreshadow.md)\n{foreshadow}\n")
        payoff = context.get("payoff", "")
        if payoff:
            parts.append(f"\n### 회수된 복선 (payoff.md)\n{payoff}\n")

        # Selected development
        dev = context.get("selected_development", "")
        if dev:
            parts.append(f"\n## 선정된 전개 방향\n{dev}\n")

        # Style reference
        style = context.get("style_reference", "")
        if style:
            parts.append(f"\n## 문체 참조\n{style}\n")

        # Episode count
        ep_count = context.get("episode_count", 0)
        if ep_count:
            parts.append(f"\n현재 {ep_count}화까지 완성.\n")

        # Revision feedback
        feedback = context.get("revision_feedback", "")
        if feedback:
            parts.append(f"\n## PD 피드백\n{feedback}\n")

        # Polishing guideline
        guideline = context.get("guideline", "")
        if guideline:
            parts.append(f"\n## 퇴고 가이드라인\n{guideline}\n")

        return "\n".join(parts)

    @staticmethod
    def load_context(project_root: Path, state) -> dict:
        """Read all context files from a project into a dict for execute().

        Args:
            project_root: Path to the project directory
            state: ProjectState instance
        """
        context = {
            "context_files": {},
            "foreshadow": "",
            "payoff": "",
            "taste_profile": "",
            "selected_development": "",
            "style_reference": state.config.get("style_reference", ""),
            "episode_count": state.episode_count,
            "revision_feedback": state.revision_feedback or "",
            "guideline": "",
        }

        # Read context/*.md files
        context_dir = project_root / "context"
        if context_dir.is_dir():
            for md_file in sorted(context_dir.glob("*.md")):
                name = md_file.name
                content = md_file.read_text(encoding="utf-8")
                if name == "foreshadow.md":
                    context["foreshadow"] = content
                elif name == "payoff.md":
                    context["payoff"] = content
                elif name == "taste_profile.md":
                    context["taste_profile"] = content
                else:
                    context["context_files"][name] = content

        # Selected development
        if state.selected_developments:
            context["selected_development"] = "\n".join(state.selected_developments)

        # Polishing guideline
        guideline_path = project_root / "polishing" / "guideline.md"
        if guideline_path.exists():
            context["guideline"] = guideline_path.read_text(encoding="utf-8")

        return context
