"""Codex CLI provider — `codex exec` reading the full prompt from stdin.

codex는 헤더/푸터 로그를 stdout에 함께 찍으므로, `--output-last-message`로
최종 메시지를 임시 파일에 받아 깨끗하게 추출한다. 산문 생성 용도이므로
샌드박스를 read-only로 고정해 레포를 건드리지 않게 한다.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from .cli_base import CLIProvider


class CodexCLIProvider(CLIProvider):
    binary = "codex"

    def _build_argv(self, exe: str, user_message: str) -> list[str]:
        fd, p = tempfile.mkstemp(suffix=".txt", prefix="codex_out_")
        os.close(fd)
        self._tmp = Path(p)
        argv = [
            exe, "exec",
            "--sandbox", "read-only",
            "--skip-git-repo-check",
            "--color", "never",
            "-o", str(self._tmp),
        ]
        if self.model:
            argv += ["-c", f"model={self.model}"]
        argv += ["-"]  # 프롬프트를 stdin에서 읽음
        return argv

    def _payload(self, system_prompt: str, user_message: str) -> str:
        return f"{system_prompt}\n\n---\n\n{user_message}"

    def _extract(self, stdout: str, stderr: str, tmp: Optional[Path]) -> str:
        if tmp and tmp.exists():
            txt = tmp.read_text(encoding="utf-8", errors="replace").strip()
            try:
                tmp.unlink()
            except OSError:
                pass
            if txt:
                return txt
        return stdout.strip()
