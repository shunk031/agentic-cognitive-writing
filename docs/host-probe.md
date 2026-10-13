# Host probe findings

Codex CLI 0.146.0 and Claude Code 2.1.236 both pass all five host checks: each host discovers workspace skills, loads a named role skill into a fresh child agent, keeps the parent's skill and user prompt out of the child, lets the parent read a file the child wrote after the child finishes, and records enough to attribute every spawn, skill injection, tool call, and file write to the parent or the child. Each host ran twice, and all four runs passed. The [host probe](../tools/host-probe/README.md) reproduces the runs and prints the tables below from harness records only.

| Check               | Codex mechanism                                                                                               | Claude Code mechanism                                                                                           |
| ------------------- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Discovery           | `.agents/skills/<name>/SKILL.md` in the workspace; `$probe-parent` in the prompt                              | `.claude/skills/<name>/SKILL.md` and `.claude/agents/<name>.md` in the workspace; `/probe-parent` in the prompt |
| Role skill in child | `spawn_agent` message that starts with `$probe-child`                                                         | `Agent` tool with `subagent_type: probe-child`; the subagent file preloads the skill through its `skills` field |
| Context isolation   | `spawn_agent` with `fork_context: false`                                                                      | Every non-fork subagent starts without the parent conversation                                                  |
| Files and lifecycle | `wait`, then `close_agent`; the parent then reads the child's file                                            | Background by default, with a completion notification; foreground with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` |
| Attribution         | One rollout file per thread, linked by `parent_thread_id`; `collab_tool_call` events name sender and receiver | One subagent transcript per child, linked to the spawning `Agent` call by `toolUseId`                           |

## Probe design

The probe uses three markers so that each check can read the records instead of the model's reply. `PPARENT-31f7` appears only in the `probe-parent` skill, `PCHILD-8d2e` appears only in the `probe-child` skill, and `PROMPT-5c19` appears only in the user prompt. The parent writes `parent.txt`, starts one child for the `probe-child` role with the message `Run your role.`, then copies `child.txt` into `parent-read.txt`. The child writes `child.txt` with its marker and replies with that marker.

Every run used a fresh workspace and a fresh host home directory inside the experiment Docker image, so no user-level guidance, skills, or plugins reached either agent. Codex used `gpt-5.6-luna` with low reasoning effort; Claude Code used `claude-haiku-4-5-20251001` with `--permission-mode dontAsk` and the tools `Read`, `Write`, `Agent`, and `Skill`.

## Codex CLI 0.146.0

Codex passed all five checks in both runs with the default `[agents]` settings. The records come from the `codex exec --json` event stream and the per-thread rollout files under `CODEX_HOME/sessions`.

| Check               | Run 1 | Run 2 |
| ------------------- | ----- | ----- |
| Discovery           | PASS  | PASS  |
| Role skill in child | PASS  | PASS  |
| Context isolation   | PASS  | PASS  |
| Files and lifecycle | PASS  | PASS  |
| Attribution         | PASS  | PASS  |

**Discovery.** Codex found both skills in the workspace without a Git repository and listed them in the parent's developer message. The `$probe-parent` mention made the harness add the skill body to the parent as a user message:

```text
- probe-parent: Host probe parent. Use only when the user invokes probe-parent by name. (file: /workspace/.agents/skills/probe-parent/SKILL.md)
<skill>
<name>probe-parent</name>
<path>/workspace/.agents/skills/probe-parent/SKILL.md</path>
```

**Role skill in child.** The child's rollout starts with the spawn message and then the harness-injected `probe-child` skill. In run 2 the child also re-read its `SKILL.md` through the shell after the injection; the check counts only the harness-injected `<skill>` message.

```text
user: $probe-child Run your role.
user: <skill>
<name>probe-child</name>
<path>/workspace/.agents/skills/probe-child/SKILL.md</path>
```

**Context isolation.** The parent called the spawn tool with `fork_context:false`, and neither the parent marker nor the prompt marker appears anywhere in the child's rollout, which also holds the child's full instructions. The probe did not run a `fork_context: true` control.

```text
tools.multi_agent_v1__spawn_agent({fork_context:false, message:"$probe-child Run your role."})
-> {"agent_id":"<child>","nickname":"Turing"}
```

**Files and lifecycle.** The event stream records `spawn_agent`, `wait`, and `close_agent` on the child, each with status `completed`, and the parent read `child.txt` only after `wait` reported the child as completed, before `close_agent` in run 1 and after it in run 2. `parent-read.txt` holds `PCHILD-8d2e`.

```text
{"type":"collab_tool_call","tool":"wait","sender_thread_id":"<parent>","receiver_thread_ids":["<child>"],
 "agents_states":{"<child>":{"status":"completed","message":"PCHILD-8d2e"}},"status":"completed"}
{"type":"collab_tool_call","tool":"close_agent", ... "status":"completed"}
```

**Attribution.** Each thread has its own rollout file. The child's `session_meta` names the parent, and every file write appears as a `patch_apply_end` event in the rollout of the thread that made it.

```text
child session_meta: "parent_thread_id":"<parent>","thread_source":"subagent",
  "source":{"subagent":{"thread_spawn":{"parent_thread_id":"<parent>","depth":1}}}
child rollout:  patch_apply_end changes {"/workspace/child.txt":{"type":"add","content":"PCHILD-8d2e\n"}}
parent rollout: patch_apply_end changes {"/workspace/parent.txt": ...}, {"/workspace/parent-read.txt": ...}
```

In this setup Codex wraps tool calls in a JavaScript `exec` tool, so the rollout records calls such as `tools.multi_agent_v1__spawn_agent(...)` inside the `exec` input rather than as separate function calls. The `collab_tool_call` items in the event stream carry the same spawn, wait, and close calls in a structured form.

## Claude Code 2.1.236

Claude Code passed all five checks in both runs. Run 1 used the default subagent mode, and run 2 set `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`. The records come from the `--output-format stream-json --verbose` event stream, the session transcript under `~/.claude/projects/`, and the subagent transcript and metadata under the session's `subagents/` directory.

| Check               | Run 1, default | Run 2, foreground |
| ------------------- | -------------- | ----------------- |
| Discovery           | PASS           | PASS              |
| Role skill in child | PASS           | PASS              |
| Context isolation   | PASS           | PASS              |
| Files and lifecycle | PASS           | PASS              |
| Attribution         | PASS           | PASS              |

**Discovery.** The `init` event lists both skills and the `probe-child` agent. `/probe-parent` in the print-mode prompt expanded to the skill body as a meta user message in the parent transcript:

```text
init: "skills": ["probe-child", "probe-parent", ...], "agents": [..., "probe-child", ...]
user: <command-name>/probe-parent</command-name><command-args>Session note: PROMPT-5c19. ...</command-args>
user (isMeta): Base directory for this skill: /workspace/.claude/skills/probe-parent
```

**Role skill in child.** The [subagent `skills` field](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents) injected the full skill into the child as a meta user message after the task prompt. The child did not call the `Skill` tool.

```text
parent: Agent {"subagent_type":"probe-child","prompt":"Run your role."}
child user: Run your role.
child user (isMeta): <command-name>probe-child</command-name><skill-format>true</skill-format>
                     Base directory for this skill: /workspace/.claude/skills/probe-child
```

**Context isolation.** Neither the parent marker nor the prompt marker appears in the child transcript. The transcript omits the system prompt, so this record covers the child's messages only. The [subagent documentation](https://code.claude.com/docs/en/sub-agents#what-loads-at-startup) states that a non-fork subagent starts with its own system prompt, the task message, the preloaded skills, and every `CLAUDE.md` file that the main conversation loads; the probe workspace had no `CLAUDE.md`.

**Files and lifecycle.** Claude Code has no close call; a child ends when it returns its reply. Print mode ran the child in the background by default, and the parent continued in a second turn when the completion notification arrived. That run emitted two `result` events; the first holds the parent's interim reply. With `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, the `Agent` call blocked until the child finished, returned the child's reply, and the run emitted one `result` event. Both runs left `PCHILD-8d2e` in `parent-read.txt`.

```text
default:    Agent result {"isAsync":true,"status":"async_launched","agentId":"<child>"}
            stream: task_started -> task_updated {"status":"completed"} -> task_notification -> parent Read child.txt
foreground: Agent result {"status":"completed","agentId":"<child>","agentType":"probe-child",
                          "content":[{"type":"text","text":"PCHILD-8d2e"}]}
```

**Attribution.** Each child has its own transcript, `subagents/agent-<child>.jsonl`, whose rows carry `isSidechain: true` and the child's `agentId`. The neighbouring metadata file links the child to the spawning call, and each `Write` call appears only in the transcript of the agent that made it.

```text
agent-<child>.meta.json: {"agentType":"probe-child","toolUseId":"<Agent call id>","spawnDepth":1}
child transcript:  Write {"file_path":"/workspace/child.txt","content":"PCHILD-8d2e"}
parent transcript: Write parent.txt, Agent, Read child.txt, Write parent-read.txt
```

Child assistant rows also carry `"attributionSkill":"probe-parent"`, the parent's active skill. Attribution should use `agentId` and the metadata file, not that field.

## What this means for the adapters

- **Skill location.** The Codex adapter places role skills under `.agents/skills/`, and the Claude Code adapter places them under `.claude/skills/` together with one `.claude/agents/<role>.md` subagent per role that preloads the role skill.
- **Role call.** The core skill names a role and the text to send; the Codex adapter turns that into `spawn_agent` with `fork_context: false` and a message that starts with `$<role>`, and the Claude Code adapter turns it into an `Agent` call with `subagent_type: <role>`.
- **Waiting.** The Codex adapter calls `wait` and then `close_agent` on every child. The Claude Code adapter either runs with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` or treats the completion notification as the end of the child; a runner reading print-mode output takes the last `result` event, not the first.
- **Hand-off.** Roles pass work through files in the workspace, and the parent reads a file only after the child has finished.
- **Records.** Behaviour checks read the Codex rollouts and `collab_tool_call` events, or the Claude Code transcripts and `subagents/*.meta.json`, and attribute actions by thread or agent ID.
- **Shared guidance.** Claude Code subagents load every `CLAUDE.md` file, so the plugin keeps role instructions in role skills, not in `CLAUDE.md`.

## Open questions

- **Shell writes.** A file written through a shell command appears only as command text, not as a structured write record, on both hosts. Step 2 should decide whether roles write only through the edit tools (`apply_patch`, `Write`) or whether checks compare workspace snapshots.
- **Workspace guidance files.** The probe workspaces had no `AGENTS.md` or `CLAUDE.md`. Whether a Codex child loads the workspace `AGENTS.md`, and how a Claude Code child avoids `CLAUDE.md` before the `omitClaudeMd` field, which needs Claude Code 2.1.271 or later, is not yet checked.
- **Negative controls.** The probe did not run `fork_context: true` on Codex or a fork subagent on Claude Code, so it shows that the chosen calls isolate the child, not that the check would catch a leak.
- **External MCP tools.** In both Claude Code runs, the parent transcript records MCP tools from outside the probe's configuration joining the parent's tool list after the session started. The adapter may need `--strict-mcp-config` or a fixed tool list to keep the tool surface stable.
- **Host versions.** The results hold for the pinned Codex CLI 0.146.0 and Claude Code 2.1.236. Newer versions need a re-run of the probe, in particular for the Claude Code background default and the Codex tool names.
- **Codex model list.** On every Codex run, the model-list response failed to parse and Codex logged an error to stderr; the runs still completed.
