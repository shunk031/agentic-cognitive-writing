# Ablation variants

Run ablations by adding a session instruction such as `Run the fixed-linear-order ablation` or by creating a temporary `.writing/ablation.md` file in the user's project. Do not fork or edit the plugin skill. The Monitor records the active variant in each trace event while the variant is active.

## Fixed linear order

Use this variant to compare the cognitive loop with a conventional order:

```text
variant: fixed-linear-order
order: planning -> translating -> reviewing
```

The Monitor enters Planning, then Translating, then Reviewing, and repeats that order for each pass. It does not choose a different next process merely because a local preference suggests one. Generate and Evaluate may still interrupt any process when new knowledge, a serious goal conflict, or the growing text requires it. Log the interruption and return to the prescribed order afterward. Keep the ordinary goal network and trace so the comparison shows which switches the full loop would have made.

## No goal network

Use this variant to test writing without hierarchical goal support:

```text
variant: no-goal-network
```

The Monitor uses the assignment as a single implicit objective and selects processes from the assignment, draft, and memory only. It does not create, develop, or regenerate hierarchical goal IDs. Keep `goals.md` unchanged if it already exists, and continue recording process switches in the trace. If the user asks to change the purpose or create a new goal, pause the ablation and ask whether to return to the full loop. Do not silently mix a partial goal network into the ablation.

## Comparing runs

Use the same assignment, starting draft, model settings, and user decisions for the full and ablated runs. Compare final text and process traces. Report process switches, interruptions, unresolved uncertainty, goal changes, and the user-visible result. The ablation is an experiment setting, not a claim that real composing is linear or goal-free.
