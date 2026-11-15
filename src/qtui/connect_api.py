import os
from pathlib import Path

from src.qtui.projects import project_manger
from src.qtui.settings_cfg import cfg


def list_projects():
    return sorted(project_manger.get_projects())


def get_active_project():
    name = cfg.currentProjectName.value
    return {
        "name": name,
        "exists": bool(name and project_manger.exist(name)),
        "structure": cfg.projectStructure.value,
    }


def list_project_files(project_name=None, relative_path=""):
    if project_name is not None and not isinstance(project_name, str):
        raise ValueError("project_name must be a string.")
    name = project_name or cfg.currentProjectName.value
    if not isinstance(relative_path, str):
        raise ValueError("relative_path must be a string.")

    if not name or name not in set(project_manger.get_projects()):
        raise ValueError(f"Unknown project: {name or '(none selected)'}")

    project_root = Path(project_manger.get_work_path(name)).resolve()
    requested_path = (project_root / relative_path).resolve()
    try:
        if os.path.commonpath((str(project_root), str(requested_path))) != str(project_root):
            raise ValueError("The requested path must stay inside the project.")
    except ValueError as error:
        raise ValueError("The requested path must stay inside the project.") from error
    if not requested_path.is_dir():
        raise ValueError(f"Project directory does not exist: {relative_path or '.'}")

    entries = sorted(requested_path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.casefold()))
    results = []
    for entry in entries[:200]:
        resolved_entry = entry.resolve()
        if os.path.commonpath((str(project_root), str(resolved_entry))) != str(project_root):
            continue
        results.append(f"{entry.name}/" if entry.is_dir() else entry.name)
    return results
