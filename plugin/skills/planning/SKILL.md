---
name: planning
description: Writes the checkable requirements of a writing task to .writing/goals.md.
---

Work in `.writing/` under the current working directory.

1. Read `task.md`, and `review.md` if it exists.
2. Take requirements from the task text only. Each requirement is one statement that a reader can mark met or unmet from the draft alone. Cover every explicit constraint in the task, such as length, sections, format, audience, and use of supplied material.
3. If `review.md` reports a requirement-level or structural problem, revise the requirements: develop one into child requirements, replace one, or add one. Keep the IDs of unchanged requirements.
4. Write `goals.md` with the file-editing tool, never through the shell. Every line has this form:

   `- G<n>: <requirement> | source: "<verbatim quote from task.md>"`

   Child requirements use IDs such as `G1.1`. Copy the quote exactly from one line of `task.md`; it must support the requirement.
5. Write in the output language the task specifies, or in the language of the task's instructions if it specifies none.
6. Write no file other than `goals.md`.
