"""데이터 모델: Phase, Step, ItemStatus 열거형 및 ProjectState."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class Phase(str, Enum):
    PHASE1 = "phase1"
    PHASE2 = "phase2"
    PHASE3 = "phase3"
    PHASE4 = "phase4"


class Step(str, Enum):
    # Phase 1
    DIRECTION_PROPOSAL = "direction_proposal"
    DIRECTION_DECISION = "direction_decision"
    PLAN_BUILDUP = "plan_buildup"
    PLAN_DECISION = "plan_decision"
    CONTEXT_CREATION = "context_creation"
    # Phase 1 - v1.5 import
    IMPORT_ANALYSIS = "import_analysis"
    IMPORT_REVIEW = "import_review"
    # Phase 2
    DEVELOPMENT_PROPOSAL = "development_proposal"
    DEVELOPMENT_DECISION = "development_decision"
    DEVELOPMENT_CONFIRM = "development_confirm"
    # Phase 3
    STYLE_SETUP = "style_setup"
    MODE_SELECTION = "mode_selection"
    WRITING = "writing"
    SCENE_DECISION = "scene_decision"
    WRITING_DECISION = "writing_decision"
    # Phase 4
    PROOFREADING = "proofreading"
    PROOFREAD_DECISION = "proofread_decision"
    CONTEXT_UPDATE = "context_update"
    CONTEXT_SIZE_CHECK = "context_size_check"
    COMPLETE = "complete"


class ItemStatus(str, Enum):
    PROPOSED = "proposed"
    SELECTED = "selected"
    HELD = "held"
    DISCARDED = "discarded"


@dataclass
class Item:
    id: int
    text: str
    status: str = ItemStatus.PROPOSED.value
    probability: Optional[float] = None

    def to_dict(self) -> dict:
        d = {"id": self.id, "text": self.text, "status": self.status}
        d["probability"] = self.probability
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Item:
        return cls(
            id=d["id"],
            text=d["text"],
            status=d.get("status", ItemStatus.PROPOSED.value),
            probability=d.get("probability"),
        )


@dataclass
class ProjectState:
    project_name: str
    novel_title: str
    phase: str = Phase.PHASE1.value
    step: str = Step.DIRECTION_PROPOSAL.value
    episode_count: int = 0
    scene_count: int = 0
    context_version: int = 0
    items: list[Item] = field(default_factory=list)
    selected_developments: list[str] = field(default_factory=list)
    config: dict = field(default_factory=lambda: {"style_reference": None, "writing_mode": None, "auto_write": False})
    revision_feedback: Optional[str] = None
    draft_files: list[str] = field(default_factory=list)
    import_file: Optional[str] = None
    # v1.7: 과거 회차 재수정 모드
    revision_mode: bool = False
    revision_episode: Optional[str] = None
    revision_return_phase: Optional[str] = None
    revision_return_step: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "novel_title": self.novel_title,
            "phase": self.phase,
            "step": self.step,
            "episode_count": self.episode_count,
            "scene_count": self.scene_count,
            "context_version": self.context_version,
            "items": [item.to_dict() for item in self.items],
            "selected_developments": self.selected_developments,
            "config": self.config,
            "revision_feedback": self.revision_feedback,
            "draft_files": self.draft_files,
            "import_file": self.import_file,
            "revision_mode": self.revision_mode,
            "revision_episode": self.revision_episode,
            "revision_return_phase": self.revision_return_phase,
            "revision_return_step": self.revision_return_step,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProjectState:
        items = [Item.from_dict(i) for i in d.get("items", [])]
        return cls(
            project_name=d["project_name"],
            novel_title=d["novel_title"],
            phase=d.get("phase", Phase.PHASE1.value),
            step=d.get("step", Step.DIRECTION_PROPOSAL.value),
            episode_count=d.get("episode_count", 0),
            scene_count=d.get("scene_count", 0),
            context_version=d.get("context_version", 0),
            items=items,
            selected_developments=d.get("selected_developments", []),
            config=cls._migrate_config(d.get("config", {"style_reference": None, "writing_mode": None, "auto_write": False})),
            revision_feedback=d.get("revision_feedback"),
            draft_files=cls._migrate_draft_files(d),
            import_file=d.get("import_file"),
            revision_mode=d.get("revision_mode", False),
            revision_episode=d.get("revision_episode"),
            revision_return_phase=d.get("revision_return_phase"),
            revision_return_step=d.get("revision_return_step"),
        )

    @staticmethod
    def _migrate_draft_files(d: dict) -> list[str]:
        if "draft_files" in d:
            return d["draft_files"]
        old = d.get("draft_file")
        return [old] if old else []

    @staticmethod
    def _migrate_config(config: dict) -> dict:
        if "writing_modes" in config:
            modes = config.pop("writing_modes")
            if modes and "writing_mode" not in config:
                first_mode = list(modes.values())[0] if modes else None
                config["writing_mode"] = first_mode
        if "writing_mode" not in config:
            config["writing_mode"] = None
        if "auto_write" not in config:
            config["auto_write"] = False
        return config

    @property
    def selected_development(self) -> Optional[str]:
        return self.selected_developments[0] if self.selected_developments else None

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> ProjectState:
        return cls.from_dict(json.loads(text))

    def next_item_id(self) -> int:
        if not self.items:
            return 1
        return max(item.id for item in self.items) + 1

    def get_item(self, item_id: int) -> Optional[Item]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def selected_count(self) -> int:
        return sum(1 for item in self.items if item.status == ItemStatus.SELECTED.value)
