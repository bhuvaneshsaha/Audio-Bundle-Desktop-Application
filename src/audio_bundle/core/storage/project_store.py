from __future__ import annotations

import json
from pathlib import Path

from audio_bundle.core.models.project import Project
from audio_bundle.core.validation.fields import assert_no_secret_fields
from audio_bundle.shared.errors import ValidationError


def save_project(project: Project, project_file: Path) -> None:
    path = Path(project_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = project.to_dict()
    assert_no_secret_fields(payload, location="project file")
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_text(serialized, encoding="utf-8")


def load_project(project_file: Path) -> Project:
    path = Path(project_file)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError("Could not read the project file.", code="project_read_error") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Project file is not valid JSON.", code="invalid_json") from exc
    assert_no_secret_fields(payload, location="project file")
    return Project.from_dict(payload)
