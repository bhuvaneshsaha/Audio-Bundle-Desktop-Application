"""Shared constants. Crypto and bundle I/O live in later milestones."""

from __future__ import annotations

PROJECT_SCHEMA_VERSION = 1
BUNDLE_FORMAT_VERSION = 1

APP_NAME = "Audio Bundle"
APP_VERSION = "0.1.0"

BUNDLE_EXTENSION = ".audiobundle"
BUNDLE_MAGIC = b"AUDIOBUNDLE\x00\x00\x00\x00\x00"  # 16 bytes
BUNDLE_FOOTER_MAGIC = b"ABDLEND\x00"

MAX_NAME_LENGTH = 200
MAX_FILENAME_LENGTH = 255
MAX_BLOCKS_PER_PROJECT = 500
MAX_ITEMS_PER_BLOCK = 2000

AUDIO_EXTENSIONS: frozenset[str] = frozenset({".mp3", ".wav", ".m4a", ".aac"})
PDF_EXTENSIONS: frozenset[str] = frozenset({".pdf"})
SUPPORTED_EXTENSIONS: frozenset[str] = AUDIO_EXTENSIONS | PDF_EXTENSIONS
