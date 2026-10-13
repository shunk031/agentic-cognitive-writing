# Author decisions for the prompt fix (2026-10-13)

The author accepted every recommended option below.

## Termination (D1, gap G1/G18)

The Monitor ends the run only after a `Reviewing` report finds no remaining required change against both the task requirements and the active goals. A pass budget caps the run; the default is 4 complete passes. When the budget runs out, the Monitor stops and returns the current draft.

## Next-process selection and the Reviewer's role (D2, gap G2/G4)

`Reviewing` evaluates the draft and makes only local revisions inside the scope it was given. It returns any finding beyond that scope as a structured finding with a recommended next process.

The Monitor chooses the next process from the findings:

| Finding                                                                                                                    | Next process                          |
| -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| Structural or goal-level problem, such as a missing required section, wrong organization, or a goal that is unmet or wrong | `Planning`                            |
| Problem localized to a passage                                                                                             | `Translating`, scoped to that passage |
| No remaining required change                                                                                               | Stop                                  |

Every role returns a structured report. The Monitor alone selects the next process.

## Output language (D3, gap G3)

Write in the language the assignment requests. If it requests none, write in the language of the assignment's instructions.

The runner appends this rule as a shared contract to every condition (A1–A12, B1, B2), so the conditions stay comparable. The Monitor passes the assignment verbatim to the roles. Each role brief states the output language explicitly.

## Delegation (D4, gap G13)

Remove the fallback clause, so the Monitor never performs a delegated role itself.

The Monitor spawns each role agent as follows:

- with `fork_context: false`;
- with a self-contained brief that gives the absolute path of the role skill;
- with the explicit statement "you are not the Monitor";
- with prohibitions on opening the Monitor skill, spawning agents, running `codex`, and writing the trace.

The child's final message is its report. The Monitor collects it with `wait_agent` and then calls `close_agent`.

The runner stages the role skills under `<workspace>/.agents/skills/` so that Codex discovers them. A run in which a role is not delegated fails. The runner pins `[agents] max_depth = 1` and `max_threads = 6`. The paper text describing the fallback will change later.

## Ablations (D5, gap G17)

Each ablation differs from A4 only in the mechanism the paper says it removes:

- **A6:** gains A4's goal-logging check.
- **A7:** keeps the one-writer, paragraph-unit design, including its one-paragraph limit if that limit is part of the design. Its extra writing-guidance and filler-removal instructions are removed.

## Memory and interruption (D6, gap G6/G7)

Remove `.writing/memory/` and the interruption and recursion text. The state is the draft, the goals, and the history, matching S_t = (D_t, G_t, H_t).

## Interactive leftovers and retrieval (D7, gap G14/G19)

Remove every user-control and ask-the-user passage from all conditions. Add an explicit no-retrieval rule to the shared contract that the runner appends to every condition.

## Process (D8)

1. Rewrite A4 and the role skills.
2. Rewrite the ablations and the shared contracts.
3. Verify through four independent reviews:
   - paper conformance;
   - a fresh defect re-audit;
   - ablation diffs;
   - a smoke test on non-evaluation prompts, with a capped budget.

Discuss a full rerun and its cost with the author after the fix is final.

## Additional verified facts that shape the fix

These come from the executed runs:

- Codex never injected a role skill. Children read their role SKILL.md by shell in about 58–60% of delegations. Every role read its skill in only 27–37% of runs.
- In A8 and A12, the Monitor read all three role skills in nearly every run.
- With `fork_context:true`, a child keeps the system, developer, and user messages but loses the tool outputs. 55% of forked children re-read the Monitor skill.
- Spawned agents were never closed, so they counted toward the limit of 6 threads.
- The runs used Codex 0.146.0, pinned in the runner's Docker image.

## D9. Simplified core method (author approval, 2026-10-13, "やりましょう")
The author approved this core method. It supersedes D2 where the two conflict, but only after the author confirms the Reviewer-editing decision.
1. `Planning` writes checkable requirements, each with an ID, to `goals.md`. Examples: required sections or items, length, audience, use of supplied material, and format. Requirements come only from the task text and never from judge rubrics.
2. `Translating` drafts or revises only the assigned requirements or sections in `draft.md`.
3. `Reviewing` judges each requirement as met or unmet, with quoted evidence from the draft. It does not edit the draft. That part is still pending the author's confirmation of the D2 reversal.
4. The `Monitor` reads the verdicts and selects one of three moves:
   - a local unmet requirement → scoped `Translating`;
   - a structural or requirement-level problem → `Planning`;
   - all requirements met → stop, with a pass cap.
5. `draft.md` is the single deliverable for the conditions that keep a draft. Process history is derived from harness-visible actions, not from logs the model writes.

Also approved: smoke and pilot runs use only non-evaluation prompts, and no tuning is done on quality.

## D10. Open decisions resolved (author, 2026-10-13, "推奨で")
- The author accepted the recommended option for every open decision 1–20 in the previous specification draft, v11.
- The author also accepted defining A7 Single-writer by the paper's construct: A8 Single-context plus a one-paragraph-per-Translating-step unit. A7 is generated from the same template as the other CogWriter-family arms. It does not inherit the executed A7 text's own goal format or its recursion text.

## D11. Working method (author, 2026-10-13)
- Aim for simple prompts whose behavior supports the paper's claims: the Monitor selects processes from state, the goal network is created, developed, and regenerated, roles are delegated to role agents running their role skills, and revision is targeted.
- Be thorough.
- Run small tests and improve quickly in short loops.
- Iteration targets process fidelity and mechanism exercise, measured from harness records on non-evaluation prompts only. Do not tune toward output quality. Freeze the design before any scored run.
