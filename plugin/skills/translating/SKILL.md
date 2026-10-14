---
name: translating
description: Writes or revises an assigned scope of .writing/draft.md to meet .writing/goals.md.
---

Work in `.writing/` under the current working directory. The request names the scope: requirement IDs or section names.

1. Read `task.md`, `goals.md`, `review.md` if it exists, and `draft.md` if it exists.
2. Write or revise only the scope so that it meets its requirements in `goals.md` and fixes the unmet `review.md` lines that concern it. Place a missing section where the task's section order puts it.
3. Leave everything outside the scope byte-identical.
4. Edit `draft.md` with the file-editing tool, never through the shell. `draft.md` holds only the deliverable text.
5. Write in the output language the task specifies, or in the language of the task's instructions if it specifies none.
6. Write no file other than `draft.md`.
