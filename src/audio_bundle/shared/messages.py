from __future__ import annotations

from audio_bundle.shared.errors import AudioBundleError


def user_message(exc: BaseException) -> str:
    if isinstance(exc, AudioBundleError):
        return exc.message
    return "Something went wrong. The operation was not completed."
