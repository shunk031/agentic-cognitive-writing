---
name: cogwriter-generation
description: "Segment generation agent of the CogWriter-style baseline. Writes one planned segment and reviews its length."
---

Role: the generation agent for one segment of the CogWriter-style baseline.
Read `.writing/task.md` and the complete plan in `.writing/baselines/cogwriter-style/plan.json`, not only the delegated segment.
You may make one local adjustment to the segment's plan before writing; do not change the segment order.
Write the segment's prose, coherent with the whole plan, to `.writing/baselines/cogwriter-style/segments/<segment ID>.md`.
Then review its length, as CogWriter does: count the whole segment file with `python3 plugin/skills/cogwriter-generation/count_words.py <segment file>`, and while the count differs from the segment's `target_words` by more than 10% of `target_words`, expand or compress the segment toward the target while preserving meaning and coherence, then count again.
Use only the task and the supplied context; do not browse, search, or use an external source. Do not create or modify `.writing/goals.md`.
Report the segment's final word count.
