from __future__ import annotations

from enum import StrEnum

from audio_bundle.core.validation.fields import suffix_for_filename
from audio_bundle.shared.constants import AUDIO_EXTENSIONS, PDF_EXTENSIONS, SUPPORTED_EXTENSIONS
from audio_bundle.shared.errors import ValidationError


class MediaType(StrEnum):
    AUDIO = "audio"
    PDF = "pdf"

    @classmethod
    def from_filename(cls, filename: str) -> MediaType:
        suffix = suffix_for_filename(filename)
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file type '{suffix}'. Import audio (mp3, wav, m4a, aac) or PDF only.",
                code="unsupported_file_type",
            )
        if suffix in PDF_EXTENSIONS:
            return cls.PDF
        if suffix in AUDIO_EXTENSIONS:
            return cls.AUDIO
        raise ValidationError(f"Unsupported file type '{suffix}'.", code="unsupported_file_type")

    def is_playable_audio(self) -> bool:
        return self is MediaType.AUDIO
