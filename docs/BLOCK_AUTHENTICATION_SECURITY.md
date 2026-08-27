# Block authentication: Windows vs custom password

This note explains how Audio Bundle protects course files when the Admin chooses **one unlock method for the whole course**. Unlock method is a project setting, not a per-block setting.

Related: [SECURITY.md](SECURITY.md) (crypto), [AUTHENTICATION.md](AUTHENTICATION.md) (Client UI), [BUNDLE_FORMAT.md](BUNDLE_FORMAT.md) (on-disk layout).

## What the Admin sets

On the project window, **Block unlock method (all blocks)** is one of:

| Method | What the Client asks for | What actually encrypts the lesson files |
| --- | --- | --- |
| **Custom password** | A password the Admin chose for that block | Argon2id of that password wraps the block’s AES key |
| **Windows authentication** | Windows user name + password, or Hello / PIN / fingerprint | The **bundle key** (from the main password) wraps the block’s AES key |
| **No password** | Nothing extra after the main password | Same wrap as Windows: bundle key wraps the block AES key |

Optional **Windows allow-list** (when method is Windows): `DOMAIN\user`, `user@domain`, or later `group:DOMAIN\Group`. An empty list means any Windows account that signs in successfully may open blocks.

Course-wide policies still apply: **open blocks in order**, and **only one unlocked block at a time**.

## Two different jobs: encryption vs authorization

**Encryption** decides who can turn ciphertext into audio/PDF bytes without using the official Client.

**Authorization** decides what the **shipped Client** will do after the main password is known.

| Method | Encryption of BlockKey | Official Client gate |
| --- | --- | --- |
| Custom password | Bound to that password (Argon2id + AES-256-GCM wrap). The main password cannot unwrap the block. | Must type the block password. |
| Windows | Bound to the **bundle key** only. The Admin never learns anyone’s Windows password, so the file cannot be wrapped with AD credentials. | Must pass LogonUser or Hello, then the allow-list. |
| None | Bound to the bundle key. | Opens after the main password (and sequential/single-active rules). |

Implications:

* Someone who knows **only** the main password cannot decrypt **custom-password** blocks without those block passwords.
* Someone who knows the main password **and** uses a modified unofficial program can decrypt **Windows** and **none** blocks without talking to Windows. Treat Windows auth as a **gate on the official Client**, plus an allow-list, not as Active Directory–bound cryptography.
* Windows Hello never puts a PIN or fingerprint template into the `.audiobundle`. Hello only proves the **currently logged-on Windows user** to the official Client.

## Custom passwords (strongest cryptographic bind)

Each custom-password block has its own random BlockKey. Generate-time wrap:

```text
block password → Argon2id (per-block salt in BKDF) → KEK_block
KEK_block → AES-256-GCM wrap of BlockKey (BWKY)
BlockKey → inner manifest + file blobs
```

Admin keeps those passwords in **session memory** only. They are not written to `project.json`. Generate Bundle writes a separate `*-passwords.txt` next to the `.audiobundle` so the list can be shared independently.

## Windows authentication (Client gate + bundle-key wrap)

Generate-time wrap:

```text
main password → Argon2id → KEK_main → wrap BundleKey
BundleKey → AES-256-GCM wrap of BlockKey (same BWKY slot, different KDF chunk)
```

At runtime the official Client:

1. Already accepted a Windows sign-in to start the app (shared PCs).
2. After the main password, asks again when opening a Windows-auth course.
3. Accepts **user name + password** via `LogonUserW` (`LOGON32_LOGON_NETWORK`), including `DOMAIN\user` and `user@upn` on a domain-joined PC.
4. Or accepts **Windows Hello / PIN / fingerprint** for the account already logged on (see below).
5. Checks the allow-list. Empty list = any authenticated Windows user.

Group entries (`group:DOMAIN\Group`) compare against groups recorded on the identity. Domain group expansion should use the logon token once machines are AD-joined.

## Windows Hello, PIN, and fingerprint

Lock-screen PIN/fingerprint proves you to **Windows** at login. The Client is a desktop program, so it must call Windows APIs again:

1. **`UserConsentVerifier`** (WinRT) — PIN, fingerprint, or face for the **current interactive user**. It cannot switch to another account on a shared PC.
2. If that API reports “not available to apps” (common for some Win32 builds even when the lock screen has Hello), the Client opens the **Windows credential dialog**. That dialog can still offer Hello / PIN / fingerprint providers, or a password.

Hello **does not** verify a different person sitting at a kiosk. Shared classroom PCs should keep using **user name and password** so the next student can sign in as themselves.

Username/password in the Client is independent of how you unlocked the PC. If Hello fails, typing `DOMAIN\user` and the Windows password remains valid.

## Main password vs block method

Every `.audiobundle` still has a **main password**. That unlocks the course outline (block names). Lesson bytes stay under each BlockKey.

Seeing the outline after the main password is intended. It is not a leak of audio/PDF content.

## What this is not

This is **not** consumer DRM. Anyone who can play audio or view a PDF on a machine can record the speaker or photograph the screen (the analog hole). A determined user with the main password and a modified client can skip Windows gates on Windows/none courses.

Goals that *are* in scope: keep media confidential at rest, detect tampering (AES-GCM + SHA-256 after decrypt), never store plaintext passwords in `project.json` or logs, and give classrooms a clear Windows vs password policy in the official apps.

## Admin checklist

* Pick **one** unlock method for the course before Generate Bundle.
* For custom passwords: set a password on every block in this Admin session.
* For Windows: optionally list allowed accounts; leave blank for any signed-in Windows user.
* Remind operators: Hello = current Windows session only; shared PCs use passwords.
