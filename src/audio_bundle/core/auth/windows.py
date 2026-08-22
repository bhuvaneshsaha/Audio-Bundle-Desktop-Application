from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from audio_bundle.core.auth.identity import WindowsIdentity
from audio_bundle.shared.errors import AuthenticationError


def parse_account(username: str) -> tuple[str, str]:
    raw = username.strip()
    if not raw:
        raise AuthenticationError("Enter a Windows user name.", code="empty_windows_user")
    if "\\" in raw:
        domain, user = raw.split("\\", 1)
        return domain.strip() or ".", user.strip()
    if "@" in raw:
        return "", raw
    return ".", raw


class WindowsAuthenticator:
    """Verify a user with a Windows username and password (LogonUser)."""

    def verify_password(self, username: str, password: str) -> WindowsIdentity:
        if sys.platform != "win32":
            raise AuthenticationError(
                "Windows authentication is only available on Windows.",
                code="windows_auth_unavailable",
            )
        if not password:
            raise AuthenticationError("Enter the Windows password.", code="empty_password")
        domain, user = parse_account(username)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        token = wintypes.HANDLE()
        LOGON32_LOGON_NETWORK = 3
        LOGON32_PROVIDER_DEFAULT = 0
        ok = advapi32.LogonUserW(
            user,
            domain or None,
            password,
            LOGON32_LOGON_NETWORK,
            LOGON32_PROVIDER_DEFAULT,
            ctypes.byref(token),
        )
        if not ok:
            raise AuthenticationError(
                "Windows user name or password is incorrect.",
                code="windows_logon_failed",
            )
        try:
            return WindowsIdentity(username=user, domain="" if domain == "." else domain, upn=user if "@" in user else "")
        finally:
            ctypes.windll.kernel32.CloseHandle(token)

    def verify_hello(self) -> WindowsIdentity:
        raise AuthenticationError(
            "Windows Hello, PIN, and fingerprint are not enabled in this build. "
            "Sign in with your Windows user name and password. "
            "Hello will verify the currently logged-on user only, so shared PCs should keep using passwords.",
            code="hello_unavailable",
        )


class DevelopmentAuthenticator:
    """Non-Windows development stand-in. Never used in the Windows Client build path."""

    def verify_password(self, username: str, password: str) -> WindowsIdentity:
        if not username.strip() or not password:
            raise AuthenticationError("Enter a Windows user name and password.", code="empty_windows_user")
        domain, user = parse_account(username)
        return WindowsIdentity(username=user, domain="" if domain == "." else domain)

    def verify_hello(self) -> WindowsIdentity:
        raise AuthenticationError(
            "Windows Hello is not available on this computer.",
            code="hello_unavailable",
        )


def default_authenticator() -> WindowsAuthenticator | DevelopmentAuthenticator:
    if sys.platform == "win32":
        return WindowsAuthenticator()
    return DevelopmentAuthenticator()
