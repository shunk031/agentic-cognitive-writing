# How the theory maps to Agentic CogWriter

`Agentic CogWriter` maps the writing model to a main skill, shared role skills, and file-backed project state.

The following diagram adapts Flower and Hayes's model from "A Cognitive Process Theory of Writing"[^1]. The model represents writing as an interaction among the task environment, the writer's long-term memory, and the writing processes. The arrows indicate information flow between processes, not a fixed sequence.

```mermaid
flowchart LR
    subgraph writers_longterm_memory["The Writer's Long-term Memory"]
        box1["Knowledge of topic,<br>audience,<br>and writing plans"]
    end

    subgraph task_environment["Task Environment"]
        subgraph the_rhetorical_problem["THE RHETORICAL PROBLEM"]
            box2["Topic<br>Audience<br>Exigency"]
        end

        subgraph text_produced_so_far["TEXT PRODUCED SO FAR"]
        end
    end

    subgraph writing_process["WRITING PROCESS"]
        direction LR

        subgraph monitor["Monitor"]
        end

        subgraph planning["Planning"]
            direction TB
            organizing["Organizing"]
            goal_setting["Goal Setting"]
            generating["Generating"]
        end

        subgraph translating["Translating"]
        end

        subgraph reviewing["Reviewing"]
            direction TB
            evaluating["Evaluating"]
            revising["Revising"]
        end
    end

    writers_longterm_memory <--> writing_process
    writing_process <--> task_environment

    monitor <--> planning
    monitor <--> translating
    monitor <--> reviewing
```

The following table maps each element of the writing model to the plugin artifact that realizes it. In this table, the rhetorical problem is the topic, audience, and reason for writing, while exigency is the situation that makes writing necessary.

| Category | Model element | Plugin artifact |
| --- | --- | --- |
| Task environment | Rhetorical problem and produced text | User project `.writing/assignment.md` and `.writing/draft.md` |
|  | Rhetorical problem: topic, audience, exigency | Sections in `.writing/assignment.md` |
|  | Produced text | User project `.writing/draft.md` |
| Writer's long-term memory | Topic and audience knowledge | User project `.writing/memory/` |
|  | Writing plans | Notes and plans in `.writing/memory/` plus `.writing/goals.md` |
| `Planning` | Process and embedded sub-processes | Shared [planning skill](../plugin/skills/planning/SKILL.md) plus [Claude planner adapter](../plugin/agents/planner.md) |
|  | Generating ideas | `Planning` skill's embedded Generate sub-process |
|  | Organizing ideas and presentation | `Planning` skill's embedded Organize sub-process |
|  | Goal-setting | `Planning` skill's embedded Goal-setting sub-process and `.writing/goals.md` |
| `Translating` | Process | Shared [translating skill](../plugin/skills/translating/SKILL.md) plus [Claude translator adapter](../plugin/agents/translator.md) |
| `Reviewing` | Process and embedded sub-processes | Shared [reviewing skill](../plugin/skills/reviewing/SKILL.md) plus [Claude reviewer adapter](../plugin/agents/reviewer.md) |
|  | Evaluating | `Reviewing` skill's embedded Evaluate sub-process |
|  | Revising | `Reviewing` skill's embedded Revise sub-process |
| `Monitor` | Orchestration role | [`plugin/skills/agentic-cog-writer/SKILL.md`](../plugin/skills/agentic-cog-writer/SKILL.md), executed by the main agent |

Agentic CogWriter follows the recursive writing process described in "A Cognitive Process Theory of Writing"[^1]. Generate and Evaluate may interrupt any process. When a sub-goal resolves, control returns to its parent goal.

[^1]: Linda Flower and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication 32(4), 1981, pp. 365-387.
    DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885) / JSTOR: [https://www.jstor.org/stable/356600](https://www.jstor.org/stable/356600)
