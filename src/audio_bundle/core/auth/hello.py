from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from audio_bundle.core.auth.identity import WindowsIdentity
from audio_bundle.shared.errors import AuthenticationError

_HELLO_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
    [Windows.Security.Credentials.UI.UserConsentVerifier,Windows.Security.Credentials.UI,ContentType=WindowsRuntime] | Out-Null
    Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
    $asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
        } |
        Select-Object -First 1
    if (-not $asTaskGeneric) { Write-Output 'ERROR:WinRT AsTask not found'; exit 3 }
    function Await-WinRT($asyncOp, [Type]$resultType) {
        $asTask = $asTaskGeneric.MakeGenericMethod($resultType)
        $task = $asTask.Invoke($null, @($asyncOp))
        $null = $task.Wait()
        if ($task.IsFaulted) { throw $task.Exception }
        $task.Result
    }
    $avail = Await-WinRT ([Windows.Security.Credentials.UI.UserConsentVerifier]::CheckAvailabilityAsync()) ([Windows.Security.Credentials.UI.UserConsentVerifierAvailability])
    Write-Output "AVAIL:$avail"
    if ("$avail" -ne 'Available') { exit 10 }
    $result = Await-WinRT ([Windows.Security.Credentials.UI.UserConsentVerifier]::RequestVerificationAsync('Sign in to Audio Bundle Client')) ([Windows.Security.Credentials.UI.UserConsentVerificationResult])
    Write-Output "RESULT:$result"
} catch {
    Write-Output ("ERROR:" + $_.Exception.Message)
    exit 2
}
"""


def current_windows_identity() -> WindowsIdentity:
    if sys.platform != "win32":
        raise AuthenticationError("Windows authentication is only available on Windows.", code="windows_auth_unavailable")
    import ctypes
    from ctypes import wintypes

    secur32 = ctypes.WinDLL("secur32", use_last_error=True)
    GetUserNameExW = secur32.GetUserNameExW
    GetUserNameExW.argtypes = [ctypes.c_int, wintypes.LPWSTR, ctypes.POINTER(ctypes.c_ulong)]
    GetUserNameExW.restype = wintypes.BOOL
    NameSamCompatible = 2
    NameUserPrincipal = 8

    def _query(name_format: int) -> str:
        size = ctypes.c_ulong(256)
        buf = ctypes.create_unicode_buffer(size.value)
        if GetUserNameExW(name_format, buf, ctypes.byref(size)):
            return buf.value
        if size.value <= 1:
            return ""
        buf = ctypes.create_unicode_buffer(size.value)
        if GetUserNameExW(name_format, buf, ctypes.byref(size)):
            return buf.value
        return ""

    sam = _query(NameSamCompatible)
    upn = _query(NameUserPrincipal)
    if "\\" in sam:
        domain, user = sam.split("\\", 1)
    else:
        domain, user = "", sam or upn
    if not user:
        raise AuthenticationError("Could not read the current Windows account.", code="windows_identity_missing")
    return WindowsIdentity(username=user, domain=domain, upn=upn)


def verify_windows_hello() -> WindowsIdentity:
    """Prompt for PIN, fingerprint, or face for the currently logged-on Windows user."""
    if sys.platform != "win32":
        raise AuthenticationError("Windows Hello is only available on Windows.", code="windows_auth_unavailable")
    last_error: AuthenticationError | None = None
    try:
        return _verify_hello_powershell()
    except AuthenticationError as exc:
        if exc.code == "hello_canceled":
            raise
        last_error = exc
    try:
        identity = _verify_hello_winsdk()
        if identity is not None:
            return identity
    except AuthenticationError as exc:
        if exc.code == "hello_canceled":
            raise
        last_error = exc
    except Exception:
        pass
    if last_error is not None:
        raise last_error
    raise AuthenticationError(
        "Windows Hello, PIN, or fingerprint could not be opened. Sign in with your user name and password.",
        code="hello_unavailable",
    )


def _verify_hello_winsdk() -> WindowsIdentity | None:
    try:
        import asyncio

        from winsdk.windows.security.credentials.ui import (  # type: ignore[import-not-found]
            UserConsentVerificationResult,
            UserConsentVerifier,
            UserConsentVerifierAvailability,
        )
    except ImportError:
        return None

    async def _run() -> str:
        availability = await UserConsentVerifier.check_availability_async()
        if availability != UserConsentVerifierAvailability.AVAILABLE:
            return f"AVAIL:{availability.name}"
        result = await UserConsentVerifier.request_verification_async("Sign in to Audio Bundle Client")
        return f"RESULT:{result.name}"

    output = asyncio.run(_run())
    _raise_from_hello_output(output)
    return current_windows_identity()


def _verify_hello_powershell() -> WindowsIdentity:
    script_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
            handle.write(_HELLO_SCRIPT)
            script_path = Path(handle.name)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-STA",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            creationflags=creationflags,
        )
    except FileNotFoundError as exc:
        raise AuthenticationError(
            "Windows Hello could not start because PowerShell was not found.",
            code="hello_unavailable",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AuthenticationError("Windows Hello timed out.", code="hello_canceled") from exc
    finally:
        if script_path is not None:
            script_path.unlink(missing_ok=True)
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    _raise_from_hello_output(output)
    return current_windows_identity()


def _raise_from_hello_output(output: str) -> None:
    text = output.strip()
    avail = ""
    result = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("AVAIL:"):
            avail = line.split(":", 1)[1].strip()
        elif line.startswith("RESULT:"):
            result = line.split(":", 1)[1].strip()
        elif line.startswith("ERROR:"):
            raise AuthenticationError(
                "Windows Hello could not start. Sign in with your user name and password.",
                code="hello_unavailable",
            )
    if result.upper() in {"VERIFIED", "USERCONSENTVERIFICATIONRESULT.VERIFIED"}:
        return
    if result.upper() in {"CANCELED", "CANCELLED", "USERCONSENTVERIFICATIONRESULT.CANCELED"}:
        raise AuthenticationError("Windows Hello was canceled.", code="hello_canceled")
    if avail and avail.upper() not in {"AVAILABLE", "USERCONSENTVERIFIERAVAILABILITY.AVAILABLE"}:
        raise AuthenticationError(_availability_message(avail), code="hello_unavailable")
    if result:
        raise AuthenticationError(
            "Windows Hello could not verify this account. Sign in with your user name and password.",
            code="hello_failed",
        )
    raise AuthenticationError(
        "Windows Hello, PIN, or fingerprint could not be opened. Sign in with your user name and password.",
        code="hello_unavailable",
    )


def _availability_message(availability: str) -> str:
    token = availability.split(".")[-1].replace("_", "").replace(" ", "").lower()
    if token in {"devicenotpresent"}:
        return (
            "This PC has no Windows Hello camera or fingerprint reader for apps, "
            "or Hello is not available to desktop programs. Sign in with your user name and password. "
            "Your Windows logon PIN still works at the lock screen."
        )
    if token in {"notconfiguredforuser"}:
        return (
            "Windows Hello is not set up for this account in Settings → Accounts → Sign-in options. "
            "You can still sign in with your user name and password."
        )
    if token in {"disabledbypolicy"}:
        return "Windows Hello is turned off by policy. Sign in with your user name and password."
    return (
        f"Windows Hello is not available ({availability}). "
        "Sign in with your user name and password."
    )
