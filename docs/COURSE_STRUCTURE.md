# Course structure (folders and blocks)

This is the implemented Admin and Client tree.

## Nodes

Two node types only:

| Type | Role |
| --- | --- |
| **Folder** | Organization. Never sequenced, never locked. |
| **Block** | The unit that unlocks, plays, and follows sequence. |

Each node has `id`, `parent_id`, `name`, `node_type` (`folder` \| `block`), and sibling `sort_order`. Folder names are labels only. `Day 1`, `AGDF.21`, and `Maintenance` are treated the same.

## One folder level

Folders are a **single top level**: Day 1, Day 2, Day 3, and so on. Nested subfolders are not used.

* **Add folder** always creates the next **top-level** day, even if Day 1 is selected. That avoids accidentally adding a subfolder under the current day.
* New root folders are named **Day 1, Day 2, Day 3**, … by creation order.
* Users may rename them to any name. Renaming does not change hierarchy, blocks, or sequencing.
* Blocks live **inside** the selected day. Sequence is among sibling blocks in that day.

Older projects with a flat block list (no folders) still load: those blocks sit at the course root and sequence among themselves.

## Sequencing

**A block sequence is scoped to its immediate parent folder. Folders are organizational only and never create a sequence themselves.**

* Each day has its own independent block sequence.
* Starting Day 2 does **not** require completing blocks in Day 1.
* Example: a learner can open `Day 2 → Block 1` while Day 1 is incomplete.
* If **open in sequence** is on, Block 2 in Day 2 still waits until Block 1 in Day 2 has been opened in this Client session.
* If **one unlocked block at a time** is on, opening any block locks the previous one (across days) and deletes its temp files.

## Client marks

Folders: **📁** expand/collapse. No lock or sequence status.

Blocks:

| Mark | Meaning |
| --- | --- |
| **🔒** | Not opened yet (default, including the first block in a day) |
| **🔓** | Currently open in this session |
| **✓** | Opened earlier in this session |

The first block in a day can be opened first, but it still shows **🔒** until the learner actually unlocks it. Expand/collapse arrows apply to folders only, not to blocks.

## Password file at generate time

Generate Bundle writes:

* `Course.audiobundle` — encrypted course
* `Course-passwords.txt` — plaintext main password and (when used) block passwords, next to the bundle

The text file is for independent sharing (print or send separately). It is **not** stored in `project.json` and is **not** inside the `.audiobundle`. Treat it like any other password list.

Related: [AUTHENTICATION.md](AUTHENTICATION.md), [BLOCK_AUTHENTICATION_SECURITY.md](BLOCK_AUTHENTICATION_SECURITY.md), [SECURITY.md](SECURITY.md).
