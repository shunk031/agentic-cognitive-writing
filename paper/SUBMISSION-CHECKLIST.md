# Submission checklist

This checklist reflects the current manuscript sources in `acl_latex.tex`, `sec/`, and `tab/` and should be refreshed again immediately before submission.

## Current review-submission state

| Item | Current state | Final check before submission |
| --- | --- | --- |
| Author block | `Anonymous ACL submission` | Keep the review PDF anonymized. |
| Repository / identifying links | No author-identifying repository link appeared in the last rendered manuscript | Re-run an anonymity-sensitive string/link sweep over the final PDF and supplementary material. |
| Human evaluation | The manuscript explicitly states that human evaluation was not conducted | Keep the claim scope and Limitations consistent unless a human study is actually added. |
| Limitations / References / Appendix | The source places Limitations after Conclusion and before References, with `\clearpage` at the start of Limitations; the last verified build placed Conclusion through page 8 and Limitations from page 9, but the current HEAD has not yet been rebuilt | Rebuild the current HEAD and recheck the page boundary against the current ARR and target-venue rules. |

The last source sweep found no `TODO` or `provisional` token in `acl_latex.tex`, `sec/`, or `tab/`. Numbered-replication vocabulary has been removed from the manuscript sources; references to the first replication are intentional scope statements. Re-run this sweep after the current prose edits before submission.

## Final gates

- Re-run the placeholder and anonymity-sensitive string/link sweep over `acl_latex.tex`, `sec/`, `tab/`, the rendered PDF, and any supplementary material.
- Preserve citation coverage, with manuscript numbers sourced through `numbers.tex` and `scripts/make_numbers.py`.
- Rebuild with `paper/tools/build-pdf.sh`, require zero overfull boxes and undefined references/citations/macros, inspect the `latexmk` log, and render all PDF pages before submission.
- Regenerate and verify `paper/build/acl_latex.md` with `paper/tools/build-markdown.sh` so the reader entry point matches the TeX manuscript.
- Confirm that the content page limit, required Limitations section, reference placement, appendix placement, anonymization, and supplementary-material rules still match the current ARR and target-venue call.
- Preserve the benchmark order WritingBench, HelloBench, DoLoMiTes and the established section/appendix ownership unless the manuscript itself is intentionally revised.
