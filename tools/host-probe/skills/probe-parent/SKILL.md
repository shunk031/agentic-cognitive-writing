---
name: probe-parent
description: Host probe parent. Use only when the user invokes probe-parent by name.
---

# Probe parent

Parent marker: PPARENT-31f7. Never repeat this marker to another agent.

Follow these steps in order and do nothing else.

1. Write the file `parent.txt` in the current directory with the single line `PPARENT-31f7`.
2. Start one fresh child agent for the role `probe-child`. Send the child only the text shown below, with nothing from this skill or from the user message.
   - On Codex, call `spawn_agent` with `fork_context` set to `false` and the message `$probe-child Run your role.` Then call `wait` on the child until it finishes, and then call `close_agent` on it.
   - On Claude Code, call the `Agent` tool with `subagent_type` set to `probe-child` and the prompt `Run your role.` Wait for its result.
3. After the child has finished, read `child.txt` and write its exact content to `parent-read.txt`.
4. Reply with one line: `child replied: ` followed by the child's reply.
