from __future__ import annotations

from pathlib import Path

from audio_bundle.core.bundle.session import ClientSession

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "Sample_Course.audiobundle"


def test_sample_bundle_opens_with_documented_passwords() -> None:
    session = ClientSession.open(SAMPLE, "sample-main")
    assert session.title == "Sample Course"
    intro = next(block for block in session.opened.manifest.blocks if block.name == "Introduction")
    session.unlock_block(intro.id, "sample-intro")
    names = [entry.display_name for entry in session.block_contents(intro.id).files]
    assert names == ["Welcome audio", "Syllabus"]
    session.close()
