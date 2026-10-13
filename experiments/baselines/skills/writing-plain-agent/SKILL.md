---
name: writing-plain-agent
description: "Experiment condition A11. Give the coding agent the writing task with one neutral working-draft instruction and no writing-process guidance. Use only for the controlled plain-agent comparison."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-plain-agent.`
>
> Say the line in your first assistant message, before any tool call. The line never appears in `.writing/draft.md` or in the final response.

# Plain agent

Write the requested document. Keep your working draft in a file in the workspace; you may plan, draft, and revise it as you see fit before returning the complete final document.

The harness also needs one record that this session ran. Run the following command once from the session working directory before the final response; it is not part of the writing task.

```bash
printf '{"timestamp":"%s","event_type":"process_switch","responsible_agent":"runner","process":"generate","from_process":null,"to_process":"generate","decision":"Plain-agent session.","evidence":[],"open_uncertainty":[]}\n' "$(date -Is)" >> .writing/trace/process.jsonl
```
