"""Application error types. User-facing code should not dump tracebacks."""

from __future__ import annotations


class AudioBundleError(Exception):
    """Base error for expected application failures."""

    def __init__(self, message: str, *, code: str = "error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ValidationError(AudioBundleError):
    def __init__(self, message: str, *, code: str = "validation_error") -> None:
        super().__init__(message, code=code)


class ModelError(ValidationError):
    def __init__(self, message: str, *, code: str = "model_error") -> None:
        super().__init__(message, code=code)


class CryptoError(AudioBundleError):
    def __init__(self, message: str, *, code: str = "crypto_error") -> None:
        super().__init__(message, code=code)


class AuthenticationError(CryptoError):
    """GCM failure, wrong password, or detected tampering. Never includes secrets."""

    def __init__(self, message: str, *, code: str = "authentication_error") -> None:
        super().__init__(message, code=code)


class BundleError(AudioBundleError):
    def __init__(self, message: str, *, code: str = "bundle_error") -> None:
        super().__init__(message, code=code)
