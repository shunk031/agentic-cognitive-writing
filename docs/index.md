---
title: Overview
description: A cognitive-process architecture for agentic long-form writing.
icon: lucide/pen-line
hide:
  - toc
---

<div class="acw-hero" markdown>

<span class="acw-eyebrow">AGENTIC COGNITIVE WRITING</span>

# Agentic CogWriter

<div class="acw-tagline">Long-form writing as an adaptive cognitive process.</div>

Agentic CogWriter is a writing assistant that **plans, drafts, reviews, and adapts** while maintaining the evolving state of a long-form writing project. Instead of committing to a fixed generation pipeline, it repeatedly decides what writing operation should happen next.

<div class="acw-hero-actions" markdown>

[Get started](installation.md){ .md-button .md-button--primary }
[How it works](theory-mapping.md){ .md-button }
[View on GitHub](https://github.com/shunk031/agentic-cognitive-writing){ .md-button }

</div>

<div class="acw-process-strip">
  <span><strong>Planning</strong></span>
  <span class="acw-process-arrow">↔</span>
  <span><strong>Translating</strong></span>
  <span class="acw-process-arrow">↔</span>
  <span><strong>Reviewing</strong></span>
  <span class="acw-process-note">coordinated by the <strong>Monitor</strong></span>
</div>

</div>

<div class="acw-architecture" markdown>

<span class="acw-eyebrow">COGNITIVE PROCESS ARCHITECTURE</span>

## The Monitor decides what happens next

Agentic CogWriter operationalizes the writing model proposed by Flower and Hayes in *A Cognitive Process Theory of Writing*. A `Monitor` coordinates `Planning`, `Translating`, and `Reviewing` rather than executing them as a fixed sequence.

Each process updates a shared writing state containing the draft, goals, memory, and process history. That evolving state then informs the next decision by the `Monitor`.

```mermaid
flowchart LR
    monitor["Monitor"]
    planning["Planning"]
    translating["Translating"]
    reviewing["Reviewing"]
    state["Writing state<br/>draft · goals · memory · history"]

    monitor --> planning --> state
    monitor --> translating --> state
    monitor --> reviewing --> state
    state --> monitor
```

<div class="acw-architecture-link" markdown>

[Read the cognitive-process mapping →](theory-mapping.md)

</div>

</div>

## Explore the project

<div class="grid cards acw-project-grid" markdown>

-   :material-rocket-launch: **Get started**

    ---

    Install Agentic CogWriter for Claude Code or Codex and start a file-backed writing session.

    [Installation →](installation.md)

-   :material-brain: **How it works**

    ---

    See how the `Monitor`, `Planning`, `Translating`, `Reviewing`, writing state, and goal network map to the cognitive-process theory.

    [Cognitive process architecture →](theory-mapping.md)

-   :material-flask-outline: **Research**

    ---

    Review the research foundations behind the agent architecture, skill/subagent design, and writing evaluation methodology.

    [Research overview →](research/index.md)

-   :material-chart-box-outline: **Experiments**

    ---

    See the controlled comparison, ablations, benchmarks, evaluation protocol, and process-analysis plan.

    [Experiment overview →](experiments/index.md)

</div>
