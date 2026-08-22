# Authentication (Client and blocks)

## Client application sign-in

The Client always starts with a **Windows authentication** gate. The user must enter a Windows user name and password even if Windows is already logged on. That is intentional: more than one person may use the same classroom PC.

| Method | Status | Notes |
| --- | --- | --- |
| User name + password | Implemented | `LogonUserW` on Windows (`LOGON32_LOGON_NETWORK`). Accepts `user`, `DOMAIN\user`, and `user@upn`. |
| Windows Hello / PIN / fingerprint | Planned | Will call `UserConsentVerifier` (WinRT) to confirm the **currently logged-on** user. It cannot switch to a different account. Shared PCs should keep using typed passwords. |
| Non-Windows development | Development stand-in | Accepts any non-empty user name and password so the UI can be tested on Linux. Packaged classroom builds are Windows. |

After Active Directory join, the same password field works with domain accounts. No code change is required for basic domain logon if the PC is domain-joined and can reach a DC. Group allow-lists (`group:DOMAIN\Group`) are stored on the block; membership checks should use the token from `LogonUser` (`CheckTokenMembership`) once machines are AD-joined.

## Block unlock methods (Admin chooses per block)

1. **Custom password** — current behaviour. Argon2id wraps the block key. Required at generate time; session-only in Admin.
2. **Windows authentication** — Client asks for Windows credentials again, then checks the optional allow-list. The block key is wrapped with the **bundle key** (main password already entered). Official Client enforces Windows; this is authorization, not a cryptographic bind to the user’s AD password (the Admin never learns Windows passwords).
3. **No password** — after the Client Windows gate and the bundle main password, the block opens. Block key wrapped with the bundle key.

## Course policies (Admin checkboxes)

* **One unlocked block at a time** — opening block B locks block A and deletes A’s temp media.
* **Open in sequence** — block 2 cannot unlock until block 1 has been opened at least once in this Client session.

New projects default both on. Bundles generated without these fields stay off (older files).

## Keyboard access

Press **F1** in the Client for the shortcut list (back, browse, play/pause, seek, volume, block list).
