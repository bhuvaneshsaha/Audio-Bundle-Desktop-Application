from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from audio_bundle.core.auth.identity import WindowsIdentity
from audio_bundle.shared.errors import AuthenticationError

ERROR_CANCELLED = 1223
CREDUIWIN_ENUMERATE_CURRENT_USER = 0x200
CRED_PACK_PROTECTED_CREDENTIALS = 0x1
LOGON32_LOGON_NETWORK = 3
LOGON32_PROVIDER_DEFAULT = 0


class CREDUI_INFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hwndParent", wintypes.HWND),
        ("pszMessageText", wintypes.LPCWSTR),
        ("pszCaptionText", wintypes.LPCWSTR),
        ("hbmBanner", wintypes.HBITMAP),
    ]


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


def logon_with_password(username: str, password: str) -> WindowsIdentity:
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


def prompt_windows_credential_ui() -> WindowsIdentity:
    """System credential dialog. PIN, fingerprint, and password providers can appear here."""
    if sys.platform != "win32":
        raise AuthenticationError(
            "Windows authentication is only available on Windows.",
            code="windows_auth_unavailable",
        )
    credui = ctypes.WinDLL("credui", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    info = CREDUI_INFOW()
    info.cbSize = ctypes.sizeof(CREDUI_INFOW)
    info.hwndParent = None
    info.pszMessageText = (
        "Confirm with Windows Hello, PIN, fingerprint, or this account’s password."
    )
    info.pszCaptionText = "Audio Bundle"
    info.hbmBanner = None
    auth_package = ctypes.c_ulong(0)
    out_buf = ctypes.c_void_p()
    out_size = ctypes.c_ulong(0)
    save = wintypes.BOOL(False)
    status = credui.CredUIPromptForWindowsCredentialsW(
        ctypes.byref(info),
        0,
        ctypes.byref(auth_package),
        None,
        0,
        ctypes.byref(out_buf),
        ctypes.byref(out_size),
        ctypes.byref(save),
        CREDUIWIN_ENUMERATE_CURRENT_USER,
    )
    if status == ERROR_CANCELLED:
        raise AuthenticationError("Windows sign-in was canceled.", code="hello_canceled")
    if status != 0:
        raise AuthenticationError(
            "Windows could not open the sign-in dialog. Type the user name and password instead.",
            code="hello_unavailable",
        )
    try:
        user_len = wintypes.DWORD(256)
        domain_len = wintypes.DWORD(256)
        pass_len = wintypes.DWORD(256)
        user = ctypes.create_unicode_buffer(256)
        domain = ctypes.create_unicode_buffer(256)
        password = ctypes.create_unicode_buffer(256)
        unpacked = credui.CredUnPackAuthenticationBufferW(
            CRED_PACK_PROTECTED_CREDENTIALS,
            out_buf,
            out_size,
            user,
            ctypes.byref(user_len),
            domain,
            ctypes.byref(domain_len),
            password,
            ctypes.byref(pass_len),
        )
        if not unpacked:
            raise AuthenticationError(
                "Windows Hello completed, but the account could not be read. Type the user name and password instead.",
                code="hello_failed",
            )
        account = user.value
        if domain.value and "\\" not in account and "@" not in account:
            account = f"{domain.value}\\{account}"
        try:
            return logon_with_password(account, password.value)
        finally:
            ctypes.memset(password, 0, ctypes.sizeof(password))
    finally:
        if out_buf:
            ole32.CoTaskMemFree(out_buf)


class WindowsAuthenticator:
    """Verify a user with Windows credentials (LogonUser, Hello, or the system dialog)."""

    def verify_password(self, username: str, password: str) -> WindowsIdentity:
        return logon_with_password(username, password)

    def verify_hello(self) -> WindowsIdentity:
        from audio_bundle.core.auth.hello import verify_windows_hello

        try:
            return verify_windows_hello()
        except AuthenticationError as exc:
            if exc.code != "hello_unavailable":
                raise
            try:
                return prompt_windows_credential_ui()
            except AuthenticationError as fallback:
                if fallback.code == "hello_canceled":
                    raise
                raise exc from fallback


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
