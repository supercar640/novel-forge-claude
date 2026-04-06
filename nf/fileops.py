"""파일/디렉토리 관리: 프로젝트 생성, state 읽기/쓰기, 백업."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from .models import ProjectState


def find_project_root(start: Optional[Path] = None,
                      project_name: Optional[str] = None) -> Optional[Path]:
    """현재 디렉토리에서 state.json을 찾아 프로젝트 루트를 반환.

    탐색 우선순위:
    1. cwd 자체에 state.json이 있으면 즉시 반환
    2. cwd가 프로젝트 디렉토리 내부이면 해당 프로젝트 반환 (CWD 기반 감지)
    3. project_name 지정 시 이름으로 필터
    4. 후보가 1개면 바로 반환
    5. 여러 프로젝트가 있으면 state.json 수정 시간 기준 최신 반환
    """
    cwd = start or Path.cwd()
    # 1. 현재 디렉토리에 state.json이 있으면 바로 반환
    if (cwd / "state.json").exists():
        return cwd

    # 2. CWD 기반 감지: cwd가 프로젝트 디렉토리 내부인지 확인
    #    cwd에서 위로 올라가며 state.json이 있는 프로젝트 루트를 찾음
    for parent in cwd.parents:
        if (parent / "state.json").exists():
            if project_name and parent.name != project_name:
                break  # 이름 불일치면 아래 탐색으로
            return parent
        # NFC 루트(projects/ 폴더가 있는 곳)에 도달하면 중단
        if (parent / "projects").is_dir():
            break

    candidates: list[Path] = []

    # 3. projects/ 하위 디렉토리 탐색 (우선)
    projects_dir = cwd / "projects"
    if projects_dir.is_dir():
        for child in projects_dir.iterdir():
            if child.is_dir() and (child / "state.json").exists():
                if project_name and child.name != project_name:
                    continue
                candidates.append(child)

    # 4. 하위 디렉토리 중 state.json이 있는 곳 탐색 (1레벨만, 레거시 호환)
    if not candidates:
        for child in cwd.iterdir():
            if child.is_dir() and child != projects_dir and (child / "state.json").exists():
                if project_name and child.name != project_name:
                    continue
                candidates.append(child)

    if not candidates:
        return None

    # 5. 후보가 1개면 바로 반환, 여러 개면 mtime 기준 최신 반환
    if len(candidates) == 1:
        return candidates[0]

    candidates.sort(key=lambda p: (p / "state.json").stat().st_mtime, reverse=True)
    return candidates[0]


def find_all_projects(start: Optional[Path] = None) -> list[Path]:
    """모든 프로젝트 디렉토리 목록 반환 (최근 수정순)."""
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
    # state.json 수정 시간 기준 정렬 (최신 먼저)
    results.sort(key=lambda p: (p / "state.json").stat().st_mtime, reverse=True)
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
        (root / "shelve").mkdir()

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

    @staticmethod
    def inject_char_count(content: str) -> str:
        """기존 분량 표기가 있으면 제거하고 반환. (분량 표기 기능 비활성화)"""
        import re
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("#"):
                # 기존 분량 표기 제거
                clean = re.sub(r"\s*\(분량:\s*\d+자\)", "", line)
                lines[i] = clean
                break
        return "\n".join(lines)

    def save_episode(self, episode_num: int, content: str, prefix: str = "ep") -> Path:
        """완성 원고 저장. episodes 디렉토리에는 항상 ep### 형식으로 저장."""
        self.episodes_dir.mkdir(exist_ok=True)
        content = self.inject_char_count(content)
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

    def backup_episode(self, episode_file: str) -> Path:
        """에피소드 파일을 backup/에 날짜 형식으로 백업.

        ep003.md → ep003_backup260403.md
        이미 존재하면 ep003_backup260403_2.md, _3.md 순으로 저장.
        """
        from datetime import datetime

        self.backup_dir.mkdir(exist_ok=True)

        # 에피소드 파일 경로 확인
        ep_path = self.episodes_dir / episode_file
        if not ep_path.exists():
            raise FileNotFoundError(f"에피소드 파일이 없습니다: {ep_path}")

        # 파일명에서 확장자 분리
        stem = ep_path.stem  # ep003

        # 날짜 형식: YYMMDD
        date_str = datetime.now().strftime("%y%m%d")

        # 백업 파일명 생성
        base_backup_name = f"{stem}_backup{date_str}"
        backup_path = self.backup_dir / f"{base_backup_name}.md"

        # 중복 시 _2, _3 ... 추가
        if backup_path.exists():
            counter = 2
            while True:
                backup_path = self.backup_dir / f"{base_backup_name}_{counter}.md"
                if not backup_path.exists():
                    break
                counter += 1

        # 복사
        shutil.copy2(ep_path, backup_path)
        return backup_path

    def merge_scenes(self, scene_files: list[str]) -> Path:
        """장면 파일들을 하나의 에피소드 초안으로 병합."""
        contents = []
        for sf in scene_files:
            path = self.root / sf
            if path.exists():
                contents.append(path.read_text(encoding="utf-8"))
        merged = "\n\n".join(contents)
        return self.save_draft("ep_draft.md", merged)

    def save_to_shelve(self, text: str, item_id: int, prefix: str,
                       probability: float = None) -> Path:
        """v1.7: 보류된 항목을 shelve/ 디렉토리에 저장. 파일 경로 반환."""
        import re
        shelve_dir = self.root / "shelve"
        shelve_dir.mkdir(exist_ok=True)

        # 텍스트에서 slug 생성
        text_clean = re.sub(r"<[^>]+>", "", text[:50])
        slug = re.sub(r"[^\w\s-]", "", text_clean)
        slug = re.sub(r"\s+", "_", slug).strip("_").lower()
        if not slug:
            slug = f"item_{item_id}"

        filename = f"{prefix}_{slug}.md"
        filepath = shelve_dir / filename
        # 중복 방지
        counter = 1
        while filepath.exists():
            filename = f"{prefix}_{slug}_{counter}.md"
            filepath = shelve_dir / filename
            counter += 1

        content = f"# {prefix.capitalize()} (보류)\n\n"
        content += f"- ID: {item_id}\n"
        if probability is not None:
            content += f"- Probability: {probability}\n"
        content += f"\n{text}\n"

        filepath.write_text(content, encoding="utf-8")
        return filepath

    def file_exists(self, relative_path: str) -> bool:
        """프로젝트 루트 기준 파일 존재 확인."""
        return (self.root / relative_path).exists()

    def read_file(self, relative_path: str) -> str:
        """프로젝트 루트 기준 파일 읽기."""
        return (self.root / relative_path).read_text(encoding="utf-8")

    @staticmethod
    def count_story_chars(text: str) -> int:
        """원고 본문 글자 수 계산 (공백 포함). 마크다운 헤더, 구분선, 끝 태그, 테이블 줄 제외."""
        lines = text.split("\n")
        body_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped == "---":
                continue
            if stripped.startswith("*>"):
                continue
            if stripped.startswith("|"):
                continue
            body_lines.append(line)
        body = "\n".join(body_lines)
        return len(body)

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
