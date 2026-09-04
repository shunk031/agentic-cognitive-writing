---
title: Experiment Overview
description: Controlled evaluation of Agentic CogWriter and its writing-process architecture.
icon: lucide/flask-conical
---

# Experiments

The experiment tests whether the recursive writing-process architecture of Agentic CogWriter improves long-form writing, which architectural components matter, and whether the resulting process traces exhibit the goal dynamics predicted by the underlying cognitive theory.

The full protocol is specified before scored runs and defines the comparison conditions, data handling, evaluation, process analysis, and reporting rules.

[Read the full protocol](protocol.md){ .md-button .md-button--primary }

## Core comparison

The core experiment compares six conditions that differ in how writing is controlled and what structure evolves during composition.

| Condition | Control State | Control Unit | Decision | Evolving Structure |
| --- | --- | --- | --- | --- |
| **A1 Single-pass** | assignment + context | whole document | single generation | none |
| **A2 Staged Writing** | assignment + preceding stage outputs | fixed stage | fixed stage sequence | stage artifacts / text |
| **A3 Adaptive Task Planning** | document + task graph + task results | task node | adaptive task scheduling | task graph |
| **A4 Agentic CogWriter** | document + goal network + process history | writing process | adaptive `Monitor` | document + goals + history |
| **A5 w/o Goal Network** | document + process history | writing process | adaptive `Monitor` | document + history |
| **A6 Fixed Process Order** | document + goal network + process history | writing process | fixed process cycle | document + goals + history |

A4 is the full theory-based system. A5 and A6 isolate the contribution of the goal network and adaptive process selection.

## Research questions

The experiment asks whether:

1. the theory-based recursive architecture improves writing quality over single-pass and pipeline-style alternatives;
2. the goal network and adaptive `Monitor` independently contribute to the effect;
3. observable process traces exhibit meaningful goal creation, regeneration, process switching, and return-to-parent dynamics; and
4. the effect replicates across supported agent platforms.

## Evaluation

The protocol combines output-quality evaluation with analysis of the writing process itself.

The primary benchmark set covers broad writing tasks, long-text generation, and structured expert writing. Output evaluation uses prespecified pointwise judging as the confirmatory estimand, with pairwise comparison reported as a complementary analysis.

Process evaluation operates on the externally recorded writing trace rather than treating hidden model reasoning as data.

## Reproducibility

The experiment protocol fixes the comparison conditions, benchmark inputs, judge assignments, analysis rules, and provenance requirements before scored runs.

[Full experiment protocol →](protocol.md)
