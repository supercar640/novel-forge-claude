"""작가실(draft-room) 프리셋 — 토폴로지 × 크루 × 역할 3축 분리.

- **토폴로지(topology)**: 단계 구성 — 어떤 역할을 어떤 순서·stem으로 돌릴지. (topologies/*.json)
- **크루(crew)**: LLM 배정 — 각 역할을 누가(gemini-cli/codex-cli/claude-cli/live) 실행할지. (crews/*.json)
- **역할(role)**: 프롬프트 본문 + 기본값(온도/모드). (roles/*.md, frontmatter+body)

해석 우선순위: **프로젝트(`{project}/draft_room/`) > 빌트인(`nf/presets/draft_room/`)**.
zero-dep 유지 — JSON은 표준 라이브러리, frontmatter는 직접 파싱.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

BUILTIN_DIR = Path(__file__).parent / "presets" / "draft_room"

# 역할/단계에서 값이 비었을 때의 코드 기본값.
DEFAULT_TEMPERATURE = 0.8
DEFAULT_MODE = "auto"
DEFAULT_WORKER = {"type": "gemini-cli", "model": "", "timeout": 1800}
_WORKER_FALLBACK = {"model": "", "timeout": 1800}


class PresetError(Exception):
    """프리셋 로딩/합성 실패."""


# --------------------------------------------------------------------------- #
# frontmatter 파서 (zero-dep)
# --------------------------------------------------------------------------- #

def _coerce(value: str):
    """frontmatter 스칼라 값 형변환 (bool/int/float/str)."""
    v = value.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """선행 `---\\n...\\n---\\n` 블록을 (meta dict, body)로 분리. 없으면 ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    # 첫 줄이 '---' (앞뒤 공백 허용)
    if lines[0].strip() != "---":
        return {}, text
    meta: dict = {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = _coerce(val)
    if end is None:
        return {}, text
    body = "\n".join(lines[end + 1:]).lstrip("\n")
    return meta, body


# --------------------------------------------------------------------------- #
# 파일 해석 (프로젝트 > 빌트인)
# --------------------------------------------------------------------------- #

def _project_dir(project_root: Optional[Path]) -> Optional[Path]:
    if project_root is None:
        return None
    d = Path(project_root) / "draft_room"
    return d if d.exists() else None


def _resolve_file(project_root: Optional[Path], subdir: str, filename: str) -> tuple[Optional[Path], str]:
    """(경로, 출처) 반환. 출처 = 'project' | 'builtin'. 없으면 (None, '')."""
    pdir = _project_dir(project_root)
    if pdir:
        candidate = pdir / subdir / filename
        if candidate.exists():
            return candidate, "project"
    candidate = BUILTIN_DIR / subdir / filename
    if candidate.exists():
        return candidate, "builtin"
    return None, ""


def _list_names(project_root: Optional[Path], subdir: str, suffix: str) -> list[dict]:
    """빌트인+프로젝트의 항목 이름 나열. 프로젝트가 빌트인을 덮으면 출처='project'.

    Returns: [{"name", "source", "path"}] (이름 정렬, 중복 제거).
    """
    found: dict[str, dict] = {}
    # 빌트인 먼저
    bdir = BUILTIN_DIR / subdir
    if bdir.exists():
        for p in sorted(bdir.glob(f"*{suffix}")):
            found[p.stem] = {"name": p.stem, "source": "builtin", "path": p}
    # 프로젝트가 덮어씀
    pdir = _project_dir(project_root)
    if pdir and (pdir / subdir).exists():
        for p in sorted((pdir / subdir).glob(f"*{suffix}")):
            found[p.stem] = {"name": p.stem, "source": "project", "path": p}
    return [found[k] for k in sorted(found)]


# --------------------------------------------------------------------------- #
# 로더
# --------------------------------------------------------------------------- #

def load_role(name: str, project_root: Optional[Path] = None) -> dict:
    """역할 .md 로드 → {name, title, description, body, default_temperature, default_mode, source}."""
    path, source = _resolve_file(project_root, "roles", f"{name}.md")
    if path is None:
        raise PresetError(f"역할 '{name}' 을 찾을 수 없습니다 (roles/{name}.md).")
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return {
        "name": name,
        "title": meta.get("title", name),
        "description": meta.get("description", ""),
        "default_temperature": meta.get("default_temperature"),
        "default_mode": meta.get("default_mode"),
        "body": body.strip(),
        "source": source,
    }


def _load_json(project_root: Optional[Path], subdir: str, name: str, label: str) -> tuple[dict, str]:
    path, source = _resolve_file(project_root, subdir, f"{name}.json")
    if path is None:
        raise PresetError(f"{label} '{name}' 을 찾을 수 없습니다 ({subdir}/{name}.json).")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PresetError(f"{label} '{name}' JSON 파싱 실패: {e}") from e
    return data, source


def load_topology(name: str, project_root: Optional[Path] = None) -> dict:
    data, source = _load_json(project_root, "topologies", name, "토폴로지")
    if not isinstance(data.get("stages"), list) or not data["stages"]:
        raise PresetError(f"토폴로지 '{name}' 에 stages 가 없습니다.")
    data["_source"] = source
    return data


def load_crew(name: str, project_root: Optional[Path] = None) -> dict:
    data, source = _load_json(project_root, "crews", name, "크루")
    data.setdefault("default", dict(DEFAULT_WORKER))
    data.setdefault("workers", {})
    data["_source"] = source
    return data


def load_defaults(project_root: Optional[Path] = None) -> dict:
    """defaults.json → {topology, crew}. 프로젝트 > 빌트인."""
    path, _ = _resolve_file(project_root, "", "defaults.json")
    if path is None:
        return {"topology": "lean", "crew": "balanced"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"topology": "lean", "crew": "balanced"}
    return {
        "topology": data.get("topology", "lean"),
        "crew": data.get("crew", "balanced"),
    }


def list_topologies(project_root: Optional[Path] = None) -> list[dict]:
    out = []
    for item in _list_names(project_root, "topologies", ".json"):
        try:
            data = load_topology(item["name"], project_root)
            item["description"] = data.get("description", "")
            item["stages"] = len(data.get("stages", []))
        except PresetError:
            item["description"] = "(로드 실패)"
            item["stages"] = 0
        out.append(item)
    return out


def list_crews(project_root: Optional[Path] = None) -> list[dict]:
    out = []
    for item in _list_names(project_root, "crews", ".json"):
        try:
            data = load_crew(item["name"], project_root)
            item["description"] = data.get("description", "")
        except PresetError:
            item["description"] = "(로드 실패)"
        out.append(item)
    return out


def list_roles(project_root: Optional[Path] = None) -> list[dict]:
    out = []
    for item in _list_names(project_root, "roles", ".md"):
        try:
            role = load_role(item["name"], project_root)
            item["title"] = role["title"]
            item["description"] = role["description"]
        except PresetError:
            item["title"] = item["name"]
            item["description"] = "(로드 실패)"
        out.append(item)
    return out


# --------------------------------------------------------------------------- #
# override 파싱 (dot-path)
# --------------------------------------------------------------------------- #

def parse_overrides(override_list: Optional[list[str]]) -> dict:
    """`stakes.worker.type=codex-cli` 형태 dot-path 목록을 역할별 중첩 dict로.

    예) ["stakes.worker.type=codex-cli", "chaos.temperature=0.7", "audit.mode=auto"]
        → {"stakes": {"worker": {"type": "codex-cli"}},
           "chaos":  {"temperature": 0.7},
           "audit":  {"mode": "auto"}}
    `stakes.worker=live` 처럼 worker 전체를 'live'로 지정 가능.
    """
    result: dict = {}
    if not override_list:
        return result
    for raw in override_list:
        if "=" not in raw:
            raise PresetError(f"--override 문법 오류 (key=value 필요): {raw!r}")
        key, _, value = raw.partition("=")
        parts = [p.strip() for p in key.split(".") if p.strip()]
        if len(parts) < 2:
            raise PresetError(
                f"--override 경로는 '<역할>.<필드>' 형태여야 합니다: {raw!r}"
            )
        node = result
        for p in parts[:-1]:
            node = node.setdefault(p, {})
            if not isinstance(node, dict):
                raise PresetError(f"--override 경로 충돌: {raw!r}")
        node[parts[-1]] = _coerce(value)
    return result


# --------------------------------------------------------------------------- #
# worker 정규화 & 합성
# --------------------------------------------------------------------------- #

def _normalize_worker(spec, crew_default) -> dict:
    """worker dict 정규화 (type 필수, model/timeout 채움). crew default를 베이스로 병합."""
    base = dict(_WORKER_FALLBACK)
    if isinstance(crew_default, dict):
        base.update(crew_default)
    if isinstance(spec, dict):
        merged = {**base, **spec}
    else:
        merged = base
    merged.setdefault("model", "")
    merged.setdefault("timeout", 1800)
    if not merged.get("type"):
        raise PresetError(f"worker 에 type 이 없습니다: {spec!r}")
    return {"type": merged["type"], "model": merged.get("model", ""), "timeout": merged["timeout"]}


def _resolve_stage(stage: dict, role_def: dict, crew: dict, ov: dict) -> dict:
    role = stage["role"]
    crew_workers = crew.get("workers", {})
    crew_default = crew.get("default", dict(DEFAULT_WORKER))

    # 1) worker spec — 크루에서 가져온 뒤 override 적용
    if role in crew_workers:
        spec = crew_workers[role]
        crew_explicit = True
    else:
        spec = crew_default
        crew_explicit = False

    ow = ov.get("worker")
    override_worker = False
    if ow is not None:
        override_worker = True
        if ow == "live":
            spec = "live"
        elif isinstance(ow, dict):
            if isinstance(spec, dict):
                spec = {**spec, **ow}
            else:  # spec == "live" → 실제 worker로 승격
                base = crew_default if isinstance(crew_default, dict) else {}
                spec = {**base, **ow}
        else:
            spec = ow

    # 2) mode 결정 — 명시(override/stage) > 크루 명시 > 역할 기본 > 코드 기본
    explicit_mode = ov.get("mode") or stage.get("mode")
    if explicit_mode:
        mode = explicit_mode
    elif spec == "live":
        mode = "live"
    elif crew_explicit or override_worker:
        mode = "auto"
    elif role_def.get("default_mode"):
        mode = role_def["default_mode"]
    elif crew_default == "live":
        mode = "live"
    else:
        mode = DEFAULT_MODE

    # 3) worker 확정
    if mode == "live":
        worker = None
    else:
        base_spec = spec if isinstance(spec, dict) else crew_default
        if not isinstance(base_spec, dict):  # crew_default 마저 "live"인 극단 케이스
            base_spec = dict(DEFAULT_WORKER)
        worker = _normalize_worker(base_spec, crew_default)

    # 4) temperature / stem
    temp = stage.get("temperature")
    if temp is None:
        temp = ov.get("temperature")
    if temp is None:
        temp = role_def.get("default_temperature")
    if temp is None:
        temp = DEFAULT_TEMPERATURE

    stem = ov.get("stem") or stage.get("stem") or role

    return {
        "role": role,
        "title": role_def.get("title", role),
        "description": role_def.get("description", ""),
        "stem": stem,
        "instructions": role_def.get("body", ""),
        "mode": mode,
        "temperature": float(temp),
        "worker": worker,
    }


def compose(
    project_root: Optional[Path],
    topology_name: str,
    crew_name: str,
    overrides: Optional[dict] = None,
) -> dict:
    """토폴로지 + 크루 + 역할 → 합성된 실행 계획.

    Returns:
        {"topology", "topology_desc", "crew", "crew_desc", "stages": [resolved...]}
        resolved: {role, title, description, stem, instructions, mode, temperature, worker}
    """
    overrides = overrides or {}
    topo = load_topology(topology_name, project_root)
    crew = load_crew(crew_name, project_root)

    stages = []
    for stage in topo["stages"]:
        if "role" not in stage:
            raise PresetError(f"토폴로지 '{topology_name}' 단계에 role 이 없습니다: {stage}")
        role_def = load_role(stage["role"], project_root)
        ov = overrides.get(stage["role"], {})
        stages.append(_resolve_stage(stage, role_def, crew, ov))

    return {
        "topology": topology_name,
        "topology_desc": topo.get("description", ""),
        "topology_source": topo.get("_source", ""),
        "crew": crew_name,
        "crew_desc": crew.get("description", ""),
        "crew_source": crew.get("_source", ""),
        "stages": stages,
    }
