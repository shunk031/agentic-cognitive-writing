# Submission checklist

This checklist is regenerated from the current manuscript sources in `acl_latex.tex`, `sec/`, and `tab/`. The line numbers are current and must be refreshed after prose edits.

## Placeholders and review-only text

| Location                  | Current item                                                 | Action before submission                                     |
| ------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `acl_latex.tex:54-56`     | Named author, affiliation, and email in the author block     | Replace with the anonymized review author block.             |
| `human-eval/`             | Human validation is deferred; its packet is in `human-eval/` | Add the separate study's results before submission.          |
| `sec/08_conclusion.tex:3` | Repository link withheld for anonymous review                | Restore the artifact link after the anonymous-review period. |

The current sweep found no `TODO` or `provisional` token in `acl_latex.tex`, `sec/`, or `tab/`. Numbered-replication vocabulary has been removed from the manuscript sources; references to the first replication are intentional scope statements.

## Final gates

- Replace every item in the table before submission and rerun the placeholder search over `acl_latex.tex`, `sec/`, and `tab/`.
- Preserve citation coverage, with all numbers sourced through `numbers.tex` and `scripts/make_numbers.py`.
- Rebuild the PDF and Markdown paths, require zero overfull boxes and undefined references, and render every changed page with `tools/render-pages.sh` before the final review.
- Preserve the benchmark order WritingBench, HelloBench, DoLoMiTes; the section structure; the appendix ownership; and the anonymous-review author and repository settings until submission.
