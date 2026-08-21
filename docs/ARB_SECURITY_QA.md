# ARB security review — questions and answers

Audience: architecture / security review board. This is an **offline** desktop product that packages audio lessons and PDFs into a password-protected `.audiobundle`. It is **not** a DRM or licensing system.

Source of truth for mechanisms: [SECURITY.md](SECURITY.md). Flows: [SEQUENCE_DIAGRAMS.txt](SEQUENCE_DIAGRAMS.txt). On-disk layout: [BUNDLE_FORMAT.md](BUNDLE_FORMAT.md).

---

## 1. What problem does this encryption actually solve?

**Q:** If a student can still record the speaker, why encrypt at all?

**A:** Encryption targets the **bundle file at rest and in transit on USB/email**, not the analog hole. Without passwords, a copied `.audiobundle` is ciphertext. With the main password only, a copier sees the course **outline**, not lesson bytes. With a block password, they can play that block on any machine that has the Client — same as handing them a USB of MP3s, but they cannot silently harvest **other** blocks. Reviewers should judge the product as “password-sealed course archive,” not “unbreakable content protection.”

---

## 2. Is this consumer DRM or a license server?

**Q:** Can we revoke a leaked bundle or bind it to a laptop?

**A:** **No.** There is no server, no device binding, no online check. Anyone with the file and the passwords can open it forever. Revocation means **operational** controls: issue a new bundle, new passwords, and stop sending the old file. That limitation is explicit in the threat model so the board does not assume Netflix-style DRM.

---

## 3. Why is there no backend or cloud KMS?

**Q:** Would wrapping keys in a company KMS be stronger?

**A:** Stronger against **lost USB + weak password**, weaker against **air-gapped classrooms and zero ops footprint**. The requirement is fully offline, no accounts. A KMS would add identity, availability, and a new secret (API keys) on every Admin PC. Envelope encryption with Argon2id is the offline substitute: the “KMS” is the author’s password memory.

---

## 4. Why two passwords (main and per-block)?

**Q:** Is this complexity justified?

**A:** Yes, for **least privilege on the file**. Main password = catalogue. Block password = that lesson’s media. A facilitator can open the bundle to confirm the course title without receiving every block password. A leak of one block password does not unwrap other BlockKeys. If the business always uses one password everywhere, the crypto still stores **separate wraps**, so policies can diverge later without a format break.

---

## 5. Why Argon2id instead of PBKDF2 or bcrypt?

**Q:** Are we inventing cryptography?

**A:** No. We call `argon2-cffi` (PHC winner, RFC 9106) and `cryptography`’s AES-GCM. Argon2id is **memory-hard**, so GPU/ASIC password guessing is more expensive than PBKDF2 at similar interactive delay. bcrypt is a poor fit as a 32-byte KEK KDF and has a 72-byte input limit. scrypt was an acceptable REQUIREMENTS alternative; Argon2id is the current default. Parameters (64 MiB, time 3, parallelism 1) are stored **in the file** so we can raise cost later without bricking old bundles.

---

## 6. Can someone brute-force the bundle offline?

**Q:** What is the residual risk?

**A:** **Yes, always**, for any password-based offline file. We do not rate-limit an attacker who bypasses the UI and calls the library. Mitigation is **password quality + Argon2 cost**. The Client may later add UI delays; that does not bind a serious attacker. ARB should require an **operational password policy** (length, uniqueness per course, no reuse of staff logins). The app does not currently enforce complexity.

---

## 7. Why AES-256-GCM rather than ChaCha20-Poly1305?

**Q:** Hardware without AES-NI?

**A:** GCM is in the original stack list, well supported, and AES-NI is common on Windows course PCs. ChaCha20-Poly1305 is a sound alternative for a future format version. We did **not** implement AES-CBC+HMAC ourselves. Nonces are 12 random bytes per encryption; reuse with the same key would be fatal, so the writer never reuses a nonce by construction.

---

## 8. What stops an attacker from swapping chunks inside the file?

**Q:** Could they transplant a valid encrypted PDF into another block?

**A:** AES-GCM tags plus **AAD** bind ciphertext to chunk type and context (block id or blob id). A splice into the wrong slot fails authentication. After decrypt, **SHA-256** of plaintext is compared with a constant-time compare before Qt sees bytes. Unknown format versions and a mismatched footer size fail closed. This is integrity of **this format**, not protection against “play this file in VLC after decrypt.”

---

## 9. Do we distinguish “wrong password” from “tampered file”?

**Q:** Could error messages help an attacker?

**A:** On the **key wrap**, a bad tag is reported as wrong password / invalid data — a damaged wrap and a wrong password look the same, which we accept. After the wrap succeeds, a bad tag on manifests or blobs is reported as **corruption/tamper**, because the password already worked. We do **not** add extra unauthenticated checksums of ciphertext that would create a better oracle.

---

## 10. Are passwords stored in the project or the bundle?

**Q:** What if IT backs up the Admin folder?

**A:** Passwords are **not** in `project.json`, not in bundle plaintext, not in logs, not in Qt settings. Load rejects JSON keys such as `password` / `secret` / `key`. Admin block passwords exist only in **RAM** for the session so the author can Show password and Generate. **Backup of the Admin folder still contains plaintext audio/PDF.** That folder must be treated like a secrets share (disk encryption, access control). Only `.audiobundle` is meant for clients.

---

## 11. Why does the Client write decrypted files to disk?

**Q:** Is that a leak?

**A:** Qt’s audio and PDF stacks typically need a path. We use a **process-private** temp directory (`0700`), per-file `0600`, random names, deleted on bundle close and app exit. Residual risk: OS swap, crash dumps, forensic recovery, and the media plugin keeping buffers. Stronger options (in-memory only, overwrite-on-delete) are future hardening, not a claim we make today.

---

## 12. Can the Admin app encrypt files outside the project (path traversal)?

**Q:** Malicious `project.json`?

**A:** Relative paths only; `..` and absolute/drive paths are rejected. The writer resolves paths and refuses anything outside the project root. Imports copy into `blocks/`. This is a **malicious project file** control, not a sandbox of the whole OS.

---

## 13. What is in the clear after the main password?

**Q:** Data classification of the outline?

**A:** Course title, block **names**, order, ids, format version. Not filenames, not blob ids, not media. If block titles are sensitive (student names, unreleased product names), authors must not put that only in the block title, or they must treat the main password as equally sensitive.

---

## 14. Is the custom file format a risk vs ZIP/7z?

**Q:** Why not a well-known archive?

**A:** Password ZIP has a long history of weak modes (ZipCrypto). A dedicated parser lets us **refuse** ZIP confusion and unknown versions. The trade-off is a smaller ecosystem and the need to maintain a reader. Format v1 is documented; unsupported versions fail closed rather than “best effort” decode.

---

## 15. How are dependencies and packaged EXEs trusted?

**Q:** Supply chain?

**A:** Runtime crypto is `cryptography` + `argon2-cffi`. PyInstaller produces Admin/Client binaries. Today we do **not** claim reproducible builds or Windows Authenticode. Future ARB-friendly controls: pin hashes at pack time, SBOM, code-sign the two executables, and restrict who can run Generate Bundle.

---

## 16. Does Show password weaken security?

**Q:** Shoulder surfing in Admin?

**A:** It is an **author convenience** to verify the string before generate (passwords are never persisted). Risk is visual exposure on the Admin workstation. Alternative is type-twice confirmation only; we already confirm the **main** password at generate. Block Show password should be used on a private screen.

---

## 17. What happens in process memory?

**Q:** Can an attacker dump RAM?

**A:** While a block is unlocked, BlockKeys and plaintext exist in RAM (and often in the media decoder). Python cannot reliably mlock/wipe secrets. We treat RAM inspection as **out of scope**, same as any media player. Closing the bundle drops references and deletes the temp directory; it is not a certified wipe.

---

## 18. What would a future hardening roadmap look like (not in this release)?

**Q:** If the board asks for a next increment?

**A:** In rough value order: (1) enforced password quality at generate; (2) raise Argon2 memory after a hardware survey; (3) Admin re-wrap passwords without rebuilding blobs; (4) pin/sign packages; (5) overwrite temp files; (6) optional OS keychain for Admin session; (7) format v2 with stronger KDF floor and optional ChaCha20. None of these replace a weak password or stop recording.

---

## 19. What should the board require operationally?

**Q:** Controls outside the repo?

**A:**

- Strong, unique main and block passwords; treat them like exam-paper seals.
- Disk encryption and restricted ACLs on Admin workstations and project folders.
- Distribute `.audiobundle` + passwords on **separate** channels when feasible.
- When a course is retired, stop distributing that file; assume old copies still open.
- Do not store passwords in email subject lines or in the Admin git repo.
- Package only from a controlled pipeline if executables are given to students.

---

## 20. Recommended ARB decision language

**Q:** How should we record the finding?

**A:** *Accepted with residual risk:* the product provides **authenticated encryption of an offline course archive** with a documented two-layer password model. It does **not** provide DRM, revocation, or protection against recording or memory capture. Residual risk of **offline password guessing** and **plaintext Admin projects** must be owned by operations (password policy and workstation encryption), not assumed solved by the application.
