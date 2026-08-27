# Authentication (Client and blocks)

## Client application sign-in

The Client always starts with a **Windows authentication** gate. Shared classroom PCs may have more than one person, so the app does not assume the already-logged-on session is the course user.

| Method | Status | Notes |
| --- | --- | --- |
| User name + password | Implemented | `LogonUserW` (`LOGON32_LOGON_NETWORK`). Accepts `user`, `DOMAIN\user`, and `user@upn`. |
| Windows Hello / PIN / fingerprint | Implemented | `UserConsentVerifier` for the **currently logged-on** user. If that API is not available to desktop apps, the Windows credential dialog is used (Hello providers or password). Hello cannot switch to a different account. Shared PCs should keep using typed passwords. |
| Non-Windows development | Development stand-in | Accepts any non-empty user name and password so the UI can be tested on Linux. Packaged classroom builds are Windows. |

After Active Directory join, the same password field works with domain accounts. No code change is required for basic domain logon if the PC is domain-joined and can reach a DC. Group allow-lists (`group:DOMAIN\Group`) are stored on the course; membership checks should use the token from `LogonUser` (`CheckTokenMembership`) once machines are AD-joined.

Details of crypto vs Client gates: [BLOCK_AUTHENTICATION_SECURITY.md](BLOCK_AUTHENTICATION_SECURITY.md).

## Block unlock method (Admin chooses once for the course)

The method applies to **every block**. It is not set per block.

1. **Custom password** — Argon2id wraps each block key. Required at generate time; session-only in Admin.
2. **Windows authentication** — Client asks for Windows credentials (or Hello for the current user), then checks the optional allow-list. The block key is wrapped with the **bundle key** (main password already entered). Official Client enforces Windows; this is authorization, not a cryptographic bind to the user’s AD password (the Admin never learns Windows passwords).
3. **No password** — after the Client Windows gate and the bundle main password, the block opens. Block key wrapped with the bundle key.

## Course policies (Admin checkboxes)

* **One unlocked block at a time** — opening block B locks block A and deletes A’s temp media.
* **Open in sequence** (default on for new projects): a block cannot open until **earlier blocks in the same folder** have been opened at least once in this session. Other folders are independent. Folders themselves are never sequenced.

New projects default both on. Bundles generated without these fields stay off (older files).

## Keyboard access

Press **F1** in the Client for the shortcut list (back, browse, play/pause, seek, volume, folder/block tree).
