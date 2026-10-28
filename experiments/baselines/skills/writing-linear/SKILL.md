---
name: writing-linear
description: "Experiment condition A2. Run one fixed Pre-Write, Write, and Re-Write pass in one session, handing each stage's output to the next. Use only for the controlled staged comparison."
---

# Staged writing

Run the frozen stages that follow this invocation in the fixed order `Pre-Write -> Write -> Re-Write`, each once, in this session; do not spawn an agent. Each stage receives the assignment, the supplied context, and the complete output of the stage before it.

1. Run `Pre-Write` and write its output to `.writing/baselines/linear/pre-write.md`.
2. Run `Write` on the `Pre-Write` output and write its output to `.writing/baselines/linear/write.md`.
3. Run `Re-Write` on the `Write` output and write its output to `.writing/draft.md`.

Do not create or modify `.writing/goals.md`. Do not skip, repeat, or add a stage. `.writing/draft.md` is the final document.
