"""CLI-based AI providers — drive external agent CLIs (gemini, codex, claude) headlessly.

각 CLI는 HTTP API 대신 subprocess로 호출된다. 대형 컨텍스트(system_prompt)는
argv 길이 제한을 피하기 위해 stdin으로 전달하고, CLI별 헤드리스 계약에 맞춘다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .base import AIProvider, AIResponse


class CLIProvider(AIProvider):
    """외부 CLI를 호출하는 프로바이더의 공통 베이스.

    서브클래스는 `binary`를 지정하고 `_build_argv` / `_payload` / `_extract`를
    필요에 맞게 오버라이드한다.
    """

    binary: str = ""
    default_timeout: int = 300

    def __init__(self, model: str = "", timeout: Optional[int] = None):
        self.model = model or ""
        self.timeout = timeout or self.default_timeout

    # --- 서브클래스 훅 ---

    def _build_argv(self, exe: str, user_message: str) -> list[str]:
        """실행할 argv를 구성한다. (exe = shutil.which로 해석된 전체 경로)"""
        raise NotImplementedError

    def _payload(self, system_prompt: str, user_message: str) -> str:
        """CLI stdin으로 흘려보낼 텍스트. 기본은 system_prompt만(나머진 argv로)."""
        return system_prompt

    def _extract(self, stdout: str, stderr: str, tmp: Optional[Path]) -> str:
        """프로세스 출력에서 본문을 추출한다. 기본은 stdout 전체."""
        return stdout.strip()

    # --- 공통 ---

    def _resolve(self) -> Optional[str]:
        return shutil.which(self.binary)

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        exe = self._resolve()
        if not exe:
            raise RuntimeError(f"{self.binary} CLI를 PATH에서 찾을 수 없습니다.")

        argv = self._build_argv(exe, user_message)
        payload = self._payload(system_prompt, user_message)
        try:
            proc = subprocess.run(
                argv,
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"{self.binary} 호출이 제한시간({self.timeout}s) 내에 끝나지 않았습니다."
            )

        content = self._extract(
            proc.stdout or "", proc.stderr or "", getattr(self, "_tmp", None)
        )
        if not content.strip():
            raise RuntimeError(
                f"{self.binary} 출력이 비어 있습니다 (rc={proc.returncode}). "
                f"stderr: {(proc.stderr or '').strip()[:300]}"
            )
        return AIResponse(
            content=content,
            model=self.name(),
            usage={},
            raw={"returncode": proc.returncode, "stderr": (proc.stderr or "")[:1000]},
        )

    def name(self) -> str:
        return f"{self.binary}-cli/{self.model or 'default'}"

    def supports_long_context(self) -> bool:
        return True

    def validate(self) -> Optional[str]:
        if self._resolve() is None:
            return f"{self.binary} CLI not found in PATH"
        return None
