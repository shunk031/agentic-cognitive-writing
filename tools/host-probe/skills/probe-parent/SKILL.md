---
name: probe-parent
description: Host probe parent. Use only when the user invokes probe-parent by name.
---

Parent marker: PPARENT-31f7. Never pass this marker to another agent.

Write files only with your file-editing tool (`apply_patch` on Codex, `Write` on Claude Code), never through the shell.

1. In the current working directory, write `parent.txt` containing `PPARENT-31f7`.
2. Start one fresh `probe-child` agent and send it nothing else from this skill or the user message.
   - Codex: `spawn_agent` with `fork_context` false and message `$probe-child Run your role.`, then `wait` for it, then `close_agent`.
   - Claude Code: the `Agent` tool with `subagent_type` `probe-child` and prompt `Run your role.`
3. After the child finishes, read `child.txt` and write its content to `parent-read.txt` in the same directory.
4. Reply `child replied: ` followed by the child's reply.
