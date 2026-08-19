from __future__ import annotations

import wave
from pathlib import Path

from audio_bundle.core.bundle import write_bundle
from audio_bundle.core.crypto import CryptoEngine, KdfProfile
from audio_bundle.core.storage import load_project

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "samples" / "admin_project"
OUTPUT = ROOT / "samples" / "Sample_Course.audiobundle"

BLOCK_PASSWORDS = {
    "22222222-2222-4222-8222-222222222222": "sample-intro",
    "55555555-5555-4555-8555-555555555555": "sample-lesson",
    "77777777-7777-4777-8777-777777777777": "sample-exercises",
}
MAIN_PASSWORD = "sample-main"


def _write_silence_wav(path: Path, frames: int = 800) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * frames)


def ensure_sample_media() -> None:
    intro = PROJECT_DIR / "blocks" / "block-001"
    lesson = PROJECT_DIR / "blocks" / "block-002"
    mp3 = intro / "welcome.mp3"
    if not mp3.exists():
        mp3.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00sample-welcome")
    wav = lesson / "lesson.wav"
    if not wav.exists():
        _write_silence_wav(wav)


def main() -> None:
    ensure_sample_media()
    project = load_project(PROJECT_DIR / "project.json")
    write_bundle(
        project,
        OUTPUT,
        main_password=MAIN_PASSWORD,
        block_passwords=BLOCK_PASSWORDS,
        source_root=PROJECT_DIR,
        engine=CryptoEngine(kdf_profile=KdfProfile.TEST),
    )
    print(f"Wrote {OUTPUT}")
    print(f"Main password: {MAIN_PASSWORD}")
    print("Block passwords: Introduction=sample-intro, Lesson 1=sample-lesson, Exercises=sample-exercises")


if __name__ == "__main__":
    main()
