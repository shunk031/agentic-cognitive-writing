# Main-text figure/table reference integrity

This note records the reader-facing rule behind `tools/check-main-float-refs.py`.

## Rule

Every figure or table that remains in the main paper must have at least one explicit reference from main-text prose outside float bodies.

Before deleting or rewriting any sentence containing `\ref{fig:...}` or `\ref{tab:...}`, check whether that sentence contains the last main-text prose reference to the float. If it is the last reference and the float remains in the main paper, preserve the reference or relocate it to another appropriate main-text sentence. Do not classify the last reference as removable navigation-only prose.

## Why this exists

During the October 2026 redundancy-trimming pass, the sentence introducing Table 1 was proposed for deletion as navigation-only prose. Table 1 otherwise had no main-text reference, so deleting that sentence would have left a main-text table that no prose directed the reader to. LaTeX would still build, so ordinary undefined-reference checks would not catch the defect.

## CI enforcement

`tools/check-main-float-refs.py` expands the manuscript before `\appendix`, finds labeled `figure`, `figure*`, `table`, and `table*` environments, removes the float bodies, and checks that each `fig:` or `tab:` label is referenced from the remaining main-text prose. References that occur only inside captions or other float bodies do not satisfy the rule.

The checker is intentionally scoped to main-text floats. Appendix reference policy remains governed separately by `tools/check-appendix-refs.py` and the manuscript handoff rules.
