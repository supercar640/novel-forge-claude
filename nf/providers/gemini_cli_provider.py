"""Gemini CLI provider — `gemini -p <instruction>` with context piped via stdin.

gemini는 stdin 입력에 `-p` 프롬프트를 이어붙여 비대화형으로 실행한다.
따라서 대형 컨텍스트(system_prompt)는 stdin으로, 짧은 지시(user_message)는 -p로 전달한다.
"""

from __future__ import annotations

from .cli_base import CLIProvider


class GeminiCLIProvider(CLIProvider):
    binary = "gemini"

    def _build_argv(self, exe: str, user_message: str) -> list[str]:
        argv = [exe, "-o", "text", "-p", user_message]
        if self.model:
            argv += ["-m", self.model]
        return argv

    def _payload(self, system_prompt: str, user_message: str) -> str:
        # stdin = system/context. user_message는 -p로 stdin 뒤에 append된다.
        return system_prompt
