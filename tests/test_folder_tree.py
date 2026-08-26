from __future__ import annotations

from pathlib import Path

import pytest

from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.core.crypto import CryptoEngine, KdfProfile
from audio_bundle.core.models import Folder, NodeType, Project
from audio_bundle.core.models.block import Block
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.errors import BundleError, ValidationError


def _engine() -> CryptoEngine:
    return CryptoEngine(kdf_profile=KdfProfile.TEST)


def test_root_folders_named_day_n_and_rename_is_cosmetic(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Tree")
    first = workspace.add_folder()
    second = workspace.add_folder()
    third = workspace.add_folder()
    assert first.name == "Day 1"
    assert second.name == "Day 2"
    assert third.name == "Day 3"
    workspace.rename_folder(first.id, "Maintenance")
    workspace.rename_folder(second.id, "AGDF.21")
    assert workspace.project.get_folder(first.id).name == "Maintenance"
    nested = workspace.add_folder("URH12", parent_id=third.id)
    assert nested.parent_id == third.id
    block = workspace.add_block("Block 1", parent_id=nested.id)
    assert block.parent_id == nested.id
    restored = Project.from_dict(workspace.project.to_dict())
    assert restored.get_folder(first.id).name == "Maintenance"
    assert restored.get_block(block.id).parent_id == nested.id
    assert all(folder.node_type is NodeType.FOLDER for folder in restored.folders)


def test_max_three_folder_levels(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Depth")
    one = workspace.add_folder()
    two = workspace.add_folder("L2", parent_id=one.id)
    three = workspace.add_folder("L3", parent_id=two.id)
    assert workspace.project.folder_depth_of(three.id) == 3
    with pytest.raises(ValidationError) as exc:
        workspace.add_folder("L4", parent_id=three.id)
    assert exc.value.code == "folder_depth"
    workspace.add_block("Leaf", parent_id=three.id)


def test_sequence_is_per_parent_folder_only(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Seq")
    day1 = workspace.add_folder()
    day2 = workspace.add_folder()
    urh = workspace.add_folder("URH12", parent_id=day2.id)
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    d1b1 = workspace.add_block("Day1 Block 1", parent_id=day1.id)
    d1b2 = workspace.add_block("Day1 Block 2", parent_id=day1.id)
    d2b1 = workspace.add_block("Block 1", parent_id=urh.id)
    d2b2 = workspace.add_block("Block 2", parent_id=urh.id)
    for block in (d1b1, d1b2, d2b1, d2b2):
        workspace.import_files(block.id, [audio])
        workspace.set_block_password(block.id, "pw")
    workspace.set_sequential_unlock(True)
    workspace.set_single_active_block(False)
    bundle = tmp_path / "seq.audiobundle"
    workspace.generate_bundle(bundle, main_password="main", engine=_engine())
    session = ClientSession.open(bundle, "main")
    with pytest.raises(BundleError) as exc:
        session.unlock_block(d2b2.id, "pw")
    assert exc.value.code == "sequential_block_required"
    session.unlock_block(d2b1.id, "pw")
    assert session.is_unlocked(d2b1.id)
    session.unlock_block(d2b2.id, "pw")
    with pytest.raises(BundleError) as exc:
        session.unlock_block(d1b2.id, "pw")
    assert exc.value.code == "sequential_block_required"
    session.unlock_block(d1b1.id, "pw")
    session.close()


def test_folder_names_are_not_special() -> None:
    project = Project(name="Names")
    project.add_folder(Folder(name="Day 1"))
    project.add_folder(Folder(name="AGDF.21"))
    project.add_folder(Folder(name="Maintenance"))
    assert [folder.name for folder in project.folders] == ["Day 1", "AGDF.21", "Maintenance"]
    project.add_block(Block(name="Only", parent_id=project.folders[1].id))
    siblings = project.sibling_blocks(project.folders[0].id)
    assert siblings == []
    assert project.sibling_blocks(project.folders[1].id)[0].name == "Only"
