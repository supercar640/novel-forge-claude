"""파일/디렉토리 관리: 프로젝트 생성, state 읽기/쓰기, 백업."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from .models import ProjectState


def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """현재 디렉토리에서 state.json을 찾아 프로젝트 루트를 반환."""
    cwd = start or Path.cwd()
    state_file = cwd / "state.json"
    if state_file.exists():
        return cwd
    # projects/ 하위 디렉토리 탐색 (우선)
    projects_dir = cwd / "projects"
    if projects_dir.is_dir():
        for child in projects_dir.iterdir():
            if child.is_dir() and (child / "state.json").exists():
                return child
    # 하위 디렉토리 중 state.json이 있는 곳 탐색 (1레벨만, 레거시 호환)
    for child in cwd.iterdir():
        if child.is_dir() and (child / "state.json").exists():
            return child
    return None


def find_all_projects(start: Optional[Path] = None) -> list[Path]:
    """모든 프로젝트 디렉토리 목록 반환."""
    cwd = start or Path.cwd()
    results = []
    # projects/ 하위 탐색
    projects_dir = cwd / "projects"
    if projects_dir.is_dir():
        for child in projects_dir.iterdir():
            if child.is_dir() and (child / "state.json").exists():
                results.append(child)
    # 하위 디렉토리 탐색 (레거시 호환)
    for child in cwd.iterdir():
        if child.is_dir() and child != projects_dir and (child / "state.json").exists():
            results.append(child)
    return results


class ProjectFiles:
    """프로젝트 파일 시스템 관리."""

    def __init__(self, root: Path):
        self.root = root
        self.state_file = root / "state.json"
        self.context_dir = root / "context"
        self.episodes_dir = root / "episodes"
        self.drafts_dir = root / "drafts"
        self.backup_dir = root / "backup"

    @classmethod
    def create_project(cls, base_dir: Path, project_name: str, novel_title: str) -> ProjectFiles:
        """새 프로젝트 디렉토리 구조 생성."""
        root = base_dir / novel_title
        if root.exists():
            raise FileExistsError(f"프로젝트 디렉토리가 이미 존재합니다: {root}")

        root.mkdir(parents=True)
        (root / "context").mkdir()
        (root / "episodes").mkdir()
        (root / "drafts").mkdir()
        (root / "backup").mkdir()
        (root / "polishing").mkdir()

        state = ProjectState(project_name=project_name, novel_title=novel_title)
        pf = cls(root)
        pf.save_state(state)
        return pf

    @classmethod
    def load(cls, root: Path) -> ProjectFiles:
        """기존 프로젝트 로드."""
        if not (root / "state.json").exists():
            raise FileNotFoundError(f"state.json을 찾을 수 없습니다: {root}")
        return cls(root)

    def read_state(self) -> ProjectState:
        """state.json 읽기."""
        text = self.state_file.read_text(encoding="utf-8")
        return ProjectState.from_json(text)

    def save_state(self, state: ProjectState) -> None:
        """state.json 쓰기."""
        self.state_file.write_text(state.to_json(), encoding="utf-8")

    def save_draft(self, filename: str, content: str) -> Path:
        """초안 파일 저장."""
        self.drafts_dir.mkdir(exist_ok=True)
        filepath = self.drafts_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def save_episode(self, episode_num: int, content: str, prefix: str = "ep") -> Path:
        """완성 원고 저장. prefix로 트랙 구분 (ep=PD, auto_ep=auto)."""
        self.episodes_dir.mkdir(exist_ok=True)
        filename = f"{prefix}{episode_num:03d}.md"
        filepath = self.episodes_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def backup_context(self, version: int) -> Path:
        """현재 context/를 backup/context_v{N}/으로 복사."""
        backup_dest = self.backup_dir / f"context_v{version}"
        if backup_dest.exists():
            raise FileExistsError(f"백업이 이미 존재합니다: {backup_dest}")
        shutil.copytree(self.context_dir, backup_dest)
        return backup_dest

    def file_exists(self, relative_path: str) -> bool:
        """프로젝트 루트 기준 파일 존재 확인."""
        return (self.root / relative_path).exists()

    def read_file(self, relative_path: str) -> str:
        """프로젝트 루트 기준 파일 읽기."""
        return (self.root / relative_path).read_text(encoding="utf-8")

    @staticmethod
    def count_story_chars(text: str) -> int:
        """원고 본문 글자 수 계산. 마크다운 헤더, 구분선, 끝 태그, 테이블, 빈 줄 제외."""
        count = 0
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped == "---":
                continue
            if stripped.startswith("*>"):
                continue
            if stripped.startswith("|"):
                continue
            count += len(stripped)
        return count

    @staticmethod
    def validate_encoding(filepath: Path) -> bool:
        """파일의 UTF-8 인코딩 무결성 검증. 손상 시 False 반환."""
        try:
            text = filepath.read_text(encoding="utf-8")
            # U+FFFD (replacement character) 가 있으면 손상된 것
            if chr(0xFFFD) in text:
                return False
            # null byte 체크
            raw = filepath.read_bytes()
            if bytes([0]) in raw:
                return False
            return True
        except UnicodeDecodeError:
            return False

    def validate_context_files(self) -> list[str]:
        """context/ 폴더의 모든 md 파일 인코딩 검증. 손상된 파일명 목록 반환."""
        corrupted = []
        if not self.context_dir.is_dir():
            return corrupted
        for md_file in self.context_dir.glob("*.md"):
            if not self.validate_encoding(md_file):
                corrupted.append(md_file.name)
        return corrupted
