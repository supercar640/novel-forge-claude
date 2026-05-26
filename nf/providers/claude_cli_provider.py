"""Claude Code CLI provider — `claude -p` reading the full prompt from stdin.

하이브리드 앙상블에서는 보통 라이브 Claude Code 세션이 직접 자기 배치를
생성하지만, standalone/자동 시나리오를 위해 헤드리스 호출도 지원한다.
"""

from __future__ import annotations

from .cli_base import CLIProvider


class ClaudeCLIProvider(CLIProvider):
    binary = "claude"

    def _build_argv(self, exe: str, user_message: str) -> list[str]:
        argv = [exe, "-p", "--output-format", "text"]
        if self.model:
            argv += ["--model", self.model]
        return argv

    def _payload(self, system_prompt: str, user_message: str) -> str:
        return f"{system_prompt}\n\n---\n\n{user_message}"
