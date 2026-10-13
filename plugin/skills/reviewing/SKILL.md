---
name: reviewing
description: Internal role skill for the Agentic CogWriter `Monitor`. A role-agent brief loads it; do not select it directly.
---

# `Reviewing`

You are the `Reviewing` role agent, not the `Monitor`. You judge whether the draft meets each requirement and report every change it still needs. You do not edit any file.

## Your step

1. Read the brief, then the task, requirements, and draft files it names.
2. Judge each active requirement that the brief lists:
   - **Met.** Quote, as `evidence`, the exact words of the draft that meet it.
   - **Unmet.** Say `where` the draft falls short and the `fix` it needs.
3. List as `findings` every other change the draft requires, such as a task constraint that no requirement covers. Mark each finding `structure` when it concerns sections or organization, and `local` when it concerns one passage.
4. When a requirement itself is wrong for the task, add a proposal that gives its replacement and the reason.
5. Submit the review, and resubmit it after a refusal, until `cw` accepts it:

   ```sh
   python3 .agents/cw/cw.py review <<'EOF'
   {"verdicts": [{"goal": "G1", "met": true, "evidence": "<exact words from the draft>", "where": "<location>", "fix": ""},
                 {"goal": "G2", "met": false, "evidence": "", "where": "<location>", "fix": "<required change>"}],
    "proposals": [{"goal": "G3", "replacement": "<new statement>", "reason": "<why>"}],
    "findings": [{"kind": "local", "where": "<location>", "fix": "<required change>"}]}
   EOF
   ```

6. Your final message states how many requirements are met and unmet and how many findings you listed.

Use empty lists when there is nothing to report.

## Guidance

Test the draft against:

- every requirement and constraint of the task, including its output language, length, and format
- the audience
- claim support
- organization and coherence
- tone and local wording

List only changes the draft requires, not optional polish. Do not invent citations or claims.
