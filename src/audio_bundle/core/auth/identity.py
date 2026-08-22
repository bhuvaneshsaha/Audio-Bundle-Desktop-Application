from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WindowsIdentity:
    """Result of a successful Windows (or development) sign-in."""

    username: str
    domain: str = ""
    upn: str = ""
    groups: tuple[str, ...] = ()

    def display_name(self) -> str:
        if self.domain and self.username:
            return f"{self.domain}\\{self.username}"
        return self.username

    def aliases(self) -> set[str]:
        names = {self.username, self.display_name()}
        if self.upn:
            names.add(self.upn)
        names.update(self.groups)
        return {name.strip().casefold() for name in names if name.strip()}


def principal_allowed(identity: WindowsIdentity, allowlist: list[str]) -> bool:
    """Empty allow-list means any authenticated Windows user may proceed."""
    if not allowlist:
        return True
    aliases = identity.aliases()
    for entry in allowlist:
        token = entry.strip()
        if not token:
            continue
        lowered = token.casefold()
        if lowered.startswith("group:"):
            group = token.split(":", 1)[1].strip().casefold()
            if group in {item.casefold() for item in identity.groups}:
                return True
            continue
        if lowered in aliases:
            return True
    return False
