---
name: reviewing
description: Checks .writing/draft.md against each requirement in .writing/goals.md and writes .writing/review.md.
---

Work in `.writing/` under the current working directory.

1. Read `task.md`, `goals.md`, and `draft.md`.
2. Judge each requirement in `goals.md` against the draft as written. When a requirement states a number, count the words, sentences, paragraphs, or sections.
3. Write `review.md` with the file-editing tool, never through the shell. It holds one line per requirement, in `goals.md` order:
   - met: `- G<n>: met | evidence: "<verbatim quote from draft.md>"`
   - unmet: `- G<n>: unmet | evidence: "<verbatim quote from draft.md, or none>" | kind: local|structural | fix: <short fix>`
4. Use `kind: local` when the fix stays inside one section, and `kind: structural` when it adds, removes, or reorders sections, changes length across sections, or needs a changed requirement.
5. Copy each evidence quote exactly from one line of `draft.md`. When nothing in the draft applies, write `evidence: "none"`.
6. Write in the output language the task specifies, or in the language of the task's instructions if it specifies none.
7. Never edit `draft.md`. Write no file other than `review.md`.
