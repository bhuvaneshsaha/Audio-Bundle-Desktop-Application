from __future__ import annotations

from pathlib import Path

from audio_bundle.core.models.auth_method import BlockAuthMethod
from audio_bundle.core.models.node import NodeType
from audio_bundle.core.models.project import Project
from audio_bundle.core.models.tree import walk_tree


def password_sheet_path(bundle_path: Path) -> Path:
    """Sidecar next to the bundle, e.g. Course.audiobundle → Course-passwords.txt."""
    path = Path(bundle_path)
    return path.with_name(f"{path.stem}-passwords.txt")


def render_password_sheet(
    project: Project,
    *,
    bundle_filename: str,
    main_password: str,
    block_passwords: dict[str, str],
) -> str:
    method = project.block_auth_method
    lines = [
        "Audio Bundle — passwords",
        "",
        "Share this file independently of the .audiobundle if you want recipients",
        "to receive passwords separately. Anyone with these passwords can open",
        "the matching course content.",
        "",
        f"Course: {project.name}",
        f"Bundle file: {bundle_filename}",
        "",
        "Main password (opens the course outline):",
        f"  {main_password}",
        "",
    ]
    if method is BlockAuthMethod.PASSWORD:
        lines.append("Block passwords (custom password unlock):")
        lines.append("")
        current_folder = ""
        listed = False
        for kind, node in walk_tree(project.folders, project.blocks):
            if kind is NodeType.FOLDER:
                current_folder = node.name
                lines.append(f"{current_folder}")
                continue
            password = block_passwords.get(node.id, "")
            indent = "  " if current_folder else ""
            lines.append(f"{indent}{node.name}: {password}")
            listed = True
        if not listed:
            for block in project.blocks:
                password = block_passwords.get(block.id, "")
                lines.append(f"{block.name}: {password}")
    elif method is BlockAuthMethod.WINDOWS:
        lines.append("Block unlock: Windows authentication.")
        lines.append("Blocks do not use a custom password. Client users sign in with Windows.")
        _list_block_names(project, lines)
    else:
        lines.append("Block unlock: no password.")
        lines.append("After the main password, blocks open without a further password.")
        _list_block_names(project, lines)
    lines.append("")
    return "\n".join(lines)


def _list_block_names(project: Project, lines: list[str]) -> None:
    lines.append("")
    current_folder = ""
    for kind, node in walk_tree(project.folders, project.blocks):
        if kind is NodeType.FOLDER:
            current_folder = node.name
            lines.append(f"{current_folder}")
            continue
        indent = "  " if current_folder else ""
        lines.append(f"{indent}{node.name}")


def write_password_sheet(
    project: Project,
    bundle_path: Path,
    *,
    main_password: str,
    block_passwords: dict[str, str],
) -> Path:
    path = password_sheet_path(bundle_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_password_sheet(
        project,
        bundle_filename=Path(bundle_path).name,
        main_password=main_password,
        block_passwords=block_passwords,
    )
    path.write_text(text, encoding="utf-8")
    return path
