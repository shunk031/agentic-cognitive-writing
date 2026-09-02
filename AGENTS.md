# Repository writing guidance

This repository contains a writing plugin, research surveys, and an experiment protocol. These rules apply to all of them and to every prose deliverable, including documents, READMEs, and pull request (PR) bodies. Write those deliverables in English and use the `unslop` skill for every one.

## Cite works and link resources

Use footnotes for published works and inline links for resources.

- Give each published work a GitHub-flavored footnote marker, `[^n]`, attached directly after the named entity at first mention and at any load-bearing mention. Define the marker with the authors or organization, title, venue, year, and a DOI, arXiv, or ACL URL.
- Use inline Markdown links with descriptive labels wherever resource pointers occur, including repositories, code or data files, docs pages, dataset cards, and licenses. A name may carry both a footnote marker and nearby resource links. Leave a URL bare only when its literal string is what readers must copy or type, such as in a command, an endpoint, or a DOI identifier in a bibliography entry.
- For in-repository links, use repo-relative paths for living references or commit-pinned URLs for snapshots. Never use branch-qualified URLs such as `blob/<branch>/...`, because merged branches are deleted.

## Keep citations sparse but complete

Place enough markers to identify every cited entity without repeating them needlessly.

- Use one marker per entity per unit, where a unit is a paragraph, table row, or contiguous list. Re-mark an entity in a distant load-bearing section with the same number when needed.
- Give sibling names sharing one footnote a single group marker. Every cited entity must have at least one marker somewhere in the document.
- Do not add a labeled `Paper:` entry that duplicates a marker already attached to the entity in the same passage.

## Use lists and tables deliberately

Format content according to how readers need to use it: facts in tables, reasoning in prose, and actions in bullets.

- Use bullets for separate decisions, claims, steps, or multi-word structure. For a run of labeled links with repeated entity prefixes, use one lead-in with its marker and sub-bullets.
- Keep short atomic-token reference lists inline regardless of count. When an exact enumeration is not load-bearing, summarize it with a source link, but never summarize away content that is the claim, such as exact schema keys. Summarize third-party procedures in prose with a descriptive source link; use step lists only for procedures the reader executes.
- Put separate lines in table cells with `<br>`. Right-align only purely numeric columns; left-align text columns.
- Fragment bullets take no trailing period. Sentence bullets are punctuated. Keep each list internally consistent, and keep two-item enumerations in prose when a list adds no value.

## Make documents easy to scan

Readers should get the main answer and top caveats from a 30-second skim of the headings, first sentences, and tables.

- Use sentence-case headings and no manual section numbers. Refer to sections by name or link.
- Open each major section with its takeaway. Match the format to the content rather than forcing every point into a list.
- Expand abbreviations at first use, such as `Question Answering (QA)`. You may leave universally understood tokens such as URL, JSON, HTTP, PDF, API, CLI, README, and DOI, as well as proper names and brands such as JSTOR, arXiv, and GitHub, unexpanded.
- Avoid pronoun subjects such as "It", "This", and "They" unless the referent is the immediately preceding subject and unambiguous. Name the actor instead, as in "The survey derives ..." or "The monitor appends ...".
- Describe an artifact by its function, not with self-assessed size or effort qualifiers such as "small", "thin", "simple", or "lightweight". State platform and support scope once as a fact with concrete boundaries, rather than wording that leaves scope questions unanswered.

## Keep evidence reader-facing

Deliverables contain durable guidance for readers, not a transcript of the research process.

- Do not use bookkeeping tokens or session narration such as `VERIFIED`, `HYPOTHESIS`, or `Unverified:`. Omit research-session mechanics such as fetch fallbacks and review history.
- Express uncertainty with plain-language hedges. Keep caveats durable and reader-facing. State the criterion for inferred or evaluative claims, or hedge them, rather than asserting them without support.

## Review judgment-bearing edits

Cross-cutting edits require local judgment at every occurrence.

- Edit one occurrence at a time and review each hunk before continuing. Do not use bulk find-and-replace for judgment-bearing edits.
