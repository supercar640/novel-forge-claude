"""Gemini CLI provider — `gemini -p <instruction>` with context piped via stdin.

gemini는 stdin 입력에 `-p` 프롬프트를 이어붙여 비대화형으로 실행한다.
따라서 대형 컨텍스트(system_prompt)는 stdin으로, 짧은 지시(user_message)는 -p로 전달한다.
"""

from __future__ import annotations

from .cli_base import CLIProvider


class GeminiCLIProvider(CLIProvider):
    binary = "gemini"

    def _build_argv(self, exe: str, user_message: str) -> list[str]:
        # user_message는 stdin(_payload)으로 넘긴다. argv에는 짧은 트리거만 두어
        # Windows argv 길이 제한(약 32KB)을 피한다 — 긴 prior 원고가 들어와도 안전.
        argv = [exe, "-o", "text", "-p", "위 입력의 컨텍스트와 지시에 따라 작성해 주세요."]
        if self.model:
            argv += ["-m", self.model]
        return argv

    def _payload(self, system_prompt: str, user_message: str) -> str:
        # stdin = system/context + user_message. gemini는 stdin 뒤에 -p를 append한다.
        return f"{system_prompt}\n\n{user_message}"
