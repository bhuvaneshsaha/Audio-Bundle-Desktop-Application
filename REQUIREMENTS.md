# Build an Offline Secure Audio Bundle Desktop Application

## 1. Project Overview

Build a **fully offline desktop application in Python** for securely distributing audio lessons and PDF documents to clients.

The application is intended for **internal use**. It must not require:

* Internet access
* Cloud services
* A backend server
* A database server
* User accounts
* APIs
* External authentication services

Everything must work locally on the user's computer.

The application should have two roles/modes:

1. **Admin App** — creates and manages encrypted content bundles.
2. **Client App** — opens and consumes encrypted bundles.

Use a **single Python codebase** with shared core modules, while allowing Admin and Client applications/interfaces to be packaged separately.

---

# 2. Recommended Technology Stack

Use:

* Python 3.12+
* PySide6 for the desktop UI
* Qt Multimedia for audio playback
* Qt PDF / Qt PDF Widgets for PDF viewing
* `cryptography` for encryption
* Argon2id or scrypt for password-based key derivation
* AES-256-GCM or ChaCha20-Poly1305 for authenticated encryption
* PyInstaller for packaging

Prefer mature, well-maintained Python libraries.

Do not introduce unnecessary technologies.

The application should be designed to run completely offline.

---

# 3. Application Structure

Create these logical components:

```text
Application
│
├── Admin
│   ├── Project management
│   ├── Block management
│   ├── File management
│   ├── Drag-and-drop ordering
│   ├── Password management
│   └── Bundle generation
│
├── Client
│   ├── Bundle opening
│   ├── Main password authentication
│   ├── Block authentication
│   ├── Audio player
│   └── PDF viewer
│
└── Core
    ├── Bundle format
    ├── Manifest
    ├── Encryption
    ├── Key derivation
    ├── File handling
    └── Validation
```

Keep business logic separate from UI code.

Do not put encryption, bundle parsing, or file-management logic directly inside Qt widgets.

---

# 4. Admin Application

The Admin application should allow an administrator to create a project.

A project contains multiple blocks.

Example:

```text
Course
├── Block 1 - Introduction
├── Block 2 - Lesson 1
├── Block 3 - Lesson 2
└── Block 4 - Exercises
```

## Create Block

The administrator should be able to:

* Create a block
* Give the block a name
* Set a block password
* Add audio files
* Add PDF files
* Remove files
* Reorder files
* Rename/display friendly file names
* Save the block

Each block has its own password.

---

# 5. File Ordering

The Admin UI must support **drag-and-drop ordering**.

For example:

```text
☰ 01 Introduction.mp3
☰ 02 Lesson.mp3
☰ 03 Example.mp3
☰ 04 Exercise.pdf
☰ 05 Summary.mp3
```

The order shown in the Admin application must be stored in the bundle manifest.

The Client application must respect exactly this order.

For audio files, when one audio file finishes, the next audio file should automatically start.

Do not sort files alphabetically unless the administrator has arranged them that way.

---

# 6. Supported Files

Initially support:

### Audio

At minimum:

* MP3
* WAV
* M4A/AAC if supported reliably by the selected Qt multimedia backend

Design the application so additional formats can be added later.

### Documents

Support PDF.

Do not execute or open arbitrary files from the bundle.

Validate file types during import.

---

# 7. Bundle Generation

The Admin application must have a:

**Generate Bundle**

action.

The output should be a single custom file, for example:

```text
course_name.audiobundle
```

The bundle must contain:

* Bundle metadata
* Block metadata
* File metadata
* File ordering
* Encrypted audio files
* Encrypted PDFs
* Required cryptographic metadata

The resulting bundle must be a **single distributable file**.

The client should not need access to the original source files.

---

# 8. Bundle Security

Do NOT simply rename a ZIP file or rely on basic ZIP password protection.

Design a proper encrypted bundle format.

Use authenticated encryption.

The bundle should have a versioned format similar to:

```text
AUDIOBUNDLE
├── Header
├── Cryptographic metadata
├── Encrypted manifest
├── Encrypted block data
├── Authentication/integrity information
└── End marker / metadata
```

The exact binary format can be designed during implementation, but it must be:

* Versioned
* Documented
* Deterministic enough to test
* Tamper-detectable
* Extensible

---

# 9. Main Bundle Password

When generating a bundle, the Admin must specify a **main password**.

The Client must enter this password before the bundle can be opened.

Flow:

```text
Open .audiobundle
        ↓
Enter Main Password
        ↓
Verify password
        ↓
Decrypt/open bundle
        ↓
Show blocks
```

A wrong main password must not reveal protected content.

---

# 10. Block Passwords

Every block has its own password.

Example:

```text
Bundle
│
├── 🔒 Introduction
├── 🔒 Lesson 1
├── 🔒 Lesson 2
└── 🔒 Exercises
```

After entering the main password, the client can see the available blocks, but must enter the individual block password before accessing the block's content.

Flow:

```text
Select Block
      ↓
Enter Block Password
      ↓
Verify password
      ↓
Decrypt block
      ↓
Show audio/PDF content
```

Incorrect block passwords must not reveal the block's contents.

---

# 11. Password Storage

Never store passwords as plaintext.

Do not put plaintext passwords inside:

* The project file
* The bundle
* Logs
* Configuration files
* Source code
* Temporary files

Use a strong password-based KDF such as:

```text
Argon2id
```

or another appropriate memory-hard KDF.

Use unique random salts.

The implementation should use a cryptographically secure random number generator.

---

# 12. Encryption Architecture

Prefer an envelope-encryption architecture.

For example:

```text
Main Password
      ↓
Argon2id
      ↓
Key-encryption key
      ↓
Encrypt random bundle key
```

For blocks:

```text
Block Password
      ↓
Argon2id
      ↓
Key-encryption key
      ↓
Encrypt random block key
```

Use random encryption keys for actual content encryption.

This avoids having to re-encrypt large audio files when password metadata changes.

Use authenticated encryption such as:

```text
AES-256-GCM
```

or:

```text
ChaCha20-Poly1305
```

Do not implement cryptographic primitives manually.

---

# 13. Tamper Detection

The Client application must detect:

* Modified bundle data
* Corrupted files
* Invalid authentication tags
* Invalid manifest
* Unsupported bundle versions
* Truncated bundles

If tampering/corruption is detected, fail safely and show a clear error.

Never attempt to play corrupted/decrypted data as if it were valid.

---

# 14. Client Application

The Client application should provide a simple consumption-focused UI.

Opening a bundle:

```text
┌──────────────────────────────────────┐
│         Open Audio Bundle            │
│                                      │
│ Bundle: course.audiobundle           │
│                                      │
│ Main Password                        │
│ [________________________]           │
│                                      │
│             [ Open ]                 │
└──────────────────────────────────────┘
```

After successful authentication:

```text
┌──────────────────────────────────────┐
│ Course Name                          │
├──────────────────────────────────────┤
│ 🔒 Introduction                      │
│ 🔒 Lesson 1                          │
│ 🔒 Lesson 2                          │
│ 🔒 Exercises                         │
└──────────────────────────────────────┘
```

---

# 15. Block Unlock UI

When a block is selected:

```text
┌──────────────────────────────────────┐
│ Lesson 1                             │
│                                      │
│ Enter block password                 │
│                                      │
│ [________________________]           │
│                                      │
│             [ Unlock ]               │
└──────────────────────────────────────┘
```

After unlocking, show the block contents.

---

# 16. Audio Player

Implement a proper audio player with:

* Play
* Pause
* Stop
* Previous
* Next
* Seek backward
* Seek forward
* Seek bar
* Current position
* Duration
* Volume
* Mute
* Playback speed
* 0.5x
* 0.75x
* 1x
* 1.25x
* 1.5x
* 2x

The player should clearly show the currently playing file.

Example:

```text
Now Playing

Lesson 02.mp3

00:42 ─────────●──────────── 12:31

[ -10 ] [ Previous ] [ Play/Pause ] [ Next ] [ +10 ]

Speed: [ 1.0x ]
Volume: [████████░░]
```

---

# 17. Sequential Audio Playback

Audio playback must follow the exact Admin-defined order.

Example:

```text
01 Introduction.mp3
02 Lesson.mp3
03 Example.mp3
04 Exercise.mp3
```

When `01 Introduction.mp3` finishes:

```text
01 → 02
```

When `02` finishes:

```text
02 → 03
```

Continue until the final audio item.

PDF files in the sequence should not automatically be treated as audio.

The player should intelligently move between playable audio items while preserving the administrator's ordering.

---

# 18. PDF Viewer

The Client application must have an integrated PDF viewer.

Users should be able to:

* View PDF pages
* Zoom in/out
* Navigate pages
* Go to a specific page
* Fit page
* Fit width
* Scroll
* Search text if supported by the chosen PDF component

The PDF should be displayed inside the application rather than launching an external PDF application.

---

# 19. Temporary Decryption

Do not permanently extract decrypted content to the user's normal filesystem.

Prefer:

```text
Encrypted content
       ↓
Decrypt when required
       ↓
Use in application
       ↓
Release/cleanup
```

If temporary files are technically required by the media/PDF libraries, use a controlled temporary directory and clean it up when the content is no longer needed.

Clearly document the limitations of desktop content protection.

The goal is to prevent casual extraction and unauthorized access, not to claim impossible DRM-level protection.

---

# 20. Admin Project Files

Separate the editable Admin project from the final distributable bundle.

For example:

```text
MyCourse/
├── project.json
├── blocks/
│   ├── block-001/
│   │   ├── metadata.json
│   │   └── source files
│   ├── block-002/
│   └── block-003/
└── output/
    └── MyCourse.audiobundle
```

The Admin should be able to reopen the project and regenerate the bundle.

Do not require the administrator to recreate the project after closing the application.

---

# 21. UI/UX Requirements

The application should feel like a professional internal desktop application.

Prioritize:

* Simplicity
* Clear hierarchy
* Large readable controls
* Keyboard accessibility
* Drag-and-drop
* Clear error messages
* Progress indicators
* Confirmation dialogs for destructive operations
* Responsive UI during file processing

Never freeze the UI while:

* Encrypting large files
* Decrypting large files
* Generating bundles
* Importing files
* Calculating password KDFs

Use background workers/threads where appropriate.

---

# 22. Error Handling

Handle errors gracefully.

Examples:

* Wrong password
* Unsupported file
* Missing source file
* File permission error
* Insufficient disk space
* Corrupted bundle
* Tampered bundle
* Unsupported bundle version
* Invalid PDF
* Audio playback failure
* Bundle generation failure

Never expose Python stack traces to normal users.

Log useful diagnostic information separately without logging passwords or sensitive content.

---

# 23. Project Architecture

Use a clean architecture similar to:

```text
src/
└── audio_bundle/
    │
    ├── admin/
    │   ├── main_window.py
    │   ├── project_window.py
    │   ├── block_editor.py
    │   ├── file_list.py
    │   └── bundle_generator.py
    │
    ├── client/
    │   ├── main_window.py
    │   ├── bundle_view.py
    │   ├── block_view.py
    │   ├── audio_player.py
    │   └── pdf_viewer.py
    │
    ├── core/
    │   ├── models/
    │   ├── bundle/
    │   ├── crypto/
    │   ├── storage/
    │   └── validation/
    │
    └── shared/
        ├── constants.py
        ├── errors.py
        └── utilities.py
```

Keep UI, business logic, storage, and cryptography separate.

---

# 24. Testing

Write automated tests for the core functionality.

At minimum test:

### Encryption

* Correct password decrypts
* Incorrect password fails
* Modified ciphertext fails
* Modified authentication data fails
* Random salts are generated
* Random nonces are never reused incorrectly

### Bundles

* Create bundle
* Read bundle
* Multiple blocks
* Multiple files per block
* File ordering
* Empty block handling
* Large files
* Corrupted bundle
* Unsupported bundle version

### Client

* Main password
* Block password
* Sequential audio playback
* PDF loading
* Invalid password handling

### Admin

* Create project
* Add/remove files
* Reorder files
* Save project
* Reload project
* Generate bundle

---

# 25. Development Approach

Build this incrementally.

Do NOT attempt to create the entire application in one giant implementation.

Use these milestones:

## Milestone 1 — Core Models

Implement:

* Project
* Block
* MediaItem
* BundleManifest

Add unit tests.

## Milestone 2 — Crypto Engine

Implement:

* Password KDF
* Key generation
* Encryption
* Decryption
* Authentication
* Tamper detection

Add extensive tests before continuing.

## Milestone 3 — Bundle Engine

Implement:

* Bundle writer
* Bundle reader
* Manifest
* Versioning
* Encryption/decryption

Test independently from the UI.

## Milestone 4 — Admin UI

Implement:

* Project creation
* Block creation
* File import
* Drag/drop ordering
* Password entry
* Bundle generation

## Milestone 5 — Client UI

Implement:

* Open bundle
* Main password
* Block list
* Block password
* Content viewer

## Milestone 6 — Audio

Implement the complete audio player and sequential playback.

## Milestone 7 — PDF

Implement integrated PDF viewing.

## Milestone 8 — Packaging

Create standalone executables using PyInstaller.

---

# 26. Important Development Rules

Follow these rules throughout development:

1. Keep the application offline.
2. Do not add cloud dependencies.
3. Do not add a backend unless explicitly requested.
4. Do not invent cryptography.
5. Use established cryptographic libraries.
6. Never store plaintext passwords.
7. Never log passwords.
8. Keep crypto code independent from UI code.
9. Keep bundle parsing independent from UI code.
10. Write tests before moving to the next major subsystem.
11. Keep the bundle format versioned.
12. Make the application recover gracefully from corrupted data.
13. Do not silently discard user data.
14. Never block the UI during long-running operations.
15. Prefer simple, maintainable Python over unnecessary abstraction.
16. Do not over-engineer the first version.
17. Document important security decisions.
18. Clearly distinguish security guarantees from limitations.

---

# 27. Deliverables

The final project should include:

```text
├── Source code
├── requirements / pyproject.toml
├── Unit tests
├── Sample Admin project
├── Sample generated .audiobundle
├── README
├── Bundle format documentation
├── Security documentation
└── PyInstaller build configuration
```

The README should explain:

* How to run the Admin application
* How to run the Client application
* How to create a project
* How to generate a bundle
* How to open a bundle
* How encryption works at a high level
* How to build standalone executables

---

# 28. First Task

Do not immediately build the entire application.

First:

1. Propose the final project architecture.
2. Define the data models.
3. Define the `.audiobundle` file format.
4. Define the encryption/key hierarchy.
5. Identify any security risks or design issues.
6. Explain important technical decisions.
7. Then implement **Milestone 1 only**.
8. Add tests for Milestone 1.
9. Wait for validation before proceeding to the next milestone.

The priority is:

**Security → correctness → maintainability → speed of development → UI polish.**
