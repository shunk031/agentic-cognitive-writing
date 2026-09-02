# Repository writing guidance

## Repository scope

The repository contains a cross-platform writing plugin, research surveys, and an experiment protocol.

The writing contract covers those artifacts and every prose deliverable, including documents, READMEs, and pull request (PR) bodies; writers produce those deliverables in English with the `unslop` skill.

## Citations and links

Published works use complete footnotes, while resource pointers use descriptive Markdown links; markers identify every cited entity without needless repetition.

### Published works

- Attach each GitHub-flavored footnote marker, `[^n]`, directly after the named entity at first mention and at any load-bearing mention. Define the marker with authors or organization, title, venue, year, and a DOI, arXiv, or ACL URL.
- Use one marker per entity per unit, where a unit is a paragraph, table row, or contiguous list. Re-mark an entity in a distant load-bearing section with the same number when needed.
- Give sibling names sharing one footnote a single group marker, and give every cited entity at least one marker somewhere in the document.
- Do not add a labeled `Paper:` entry that duplicates a marker already attached to the entity in the same passage.

### Resource links

- Use descriptive Markdown links for resource pointers, including repositories, code or data files, docs pages, dataset cards, and licenses. A name may carry both its footnote marker and nearby resource links. Leave a URL bare only when its literal string is what readers must copy or type, such as in a command, an endpoint, or a DOI identifier in a bibliography entry.
- Write short runs of two to four briefly labeled links inline with slash separators, such as `[Repo](url) / [data](url) / [eval prompt](url)`.
- For longer same-entity link runs or labels needing qualifiers, use a lead-in that names the shared entity once and carries its marker, followed by a few sub-bullets. Give each sub-bullet a category label and an inline slash-separated run, and do not put a single resource link on each line.
- For in-repository links, use repo-relative paths for living references or commit-pinned URLs for snapshots. Never use branch-qualified URLs such as `blob/<branch>/...`, because a branch name is a movable pointer that can be deleted or rewritten, while a commit-pinned URL and a repository-relative path stay resolvable.
- Writers turn bare in-repository file-path mentions into relative Markdown links computed from the mentioning file's location. Writers keep runtime or user-environment paths, ground-truth tokens, and copyable command paths as plain text.

## Structure and formatting

Writers format content for reader use: facts go in tables, reasoning in prose, and actions in bullets; headings, first sentences, and tables expose the main answer and top caveats in a 30-second skim.

### Lists and prose

- Use bullets for separate decisions, claims, steps, or multi-word structure.
- Match the format to the content rather than forcing every point into a list.
- Keep short atomic-token reference lists inline regardless of count. When an exact enumeration is not load-bearing, summarize it with a source link, but never summarize away content that is the claim, such as exact schema keys. Summarize third-party procedures in prose with a descriptive source link; use step lists only for procedures the reader executes. Keep two-item enumerations in prose when a list adds no value.
- Within a scope, omit an established name from children under a lead-in, cells after a row header, and sentences inside an entity's own section. Labels carry only the differentiating part.
- Open each paragraph with a topic sentence stating its one point. Keep following sentences on that point, start a new paragraph for a new point, and make the first sentences alone carry the full argument. Merge runs of single-sentence paragraphs created by list-to-prose conversion, and use blank lines only for genuine topic shifts.
- Use bold lead-ins ending with a period for labeled prose groups, as in **Label.** New detail ..., rather than "Label:" pseudo-headers. Keep colons for genuine lists and examples.
- Fragment bullets take no trailing period; sentence bullets are punctuated. Keep each list internally consistent.

### Tables

- Use tables for atomic, comparable values. When a table cell must hold several entries, separate them with `<br>` because bullet lists do not render inside cells. When a cell needs sentences or more than about two `<br>`-separated lines, move the content to per-item subsections or prose and keep at most a compact table of atomic-value summaries. Right-align only purely numeric columns and left-align text columns.

### Headings and sections

- Use sentence-case headings and no manual section numbers. Refer to sections by name or link.
- Open each major section with its takeaway.

## Language and claim strength

Writers produce all prose deliverables in English and apply the `unslop` skill to each one.

- Expand abbreviations at first use, such as `Question Answering (QA)`. Leave universally understood tokens such as URL, JSON, HTTP, PDF, API, CLI, README, and DOI, as well as proper names and brands such as JSTOR, arXiv, and GitHub, unexpanded.
- Avoid pronoun subjects such as "It", "This", and "They" unless the referent is the immediately preceding subject and unambiguous. Name the actor instead, as in "The survey derives ..." or "The monitor appends ...".
- Describe an artifact by its function, not with self-assessed size or effort qualifiers such as "small", "thin", "simple", or "lightweight". State platform, support, and compatibility scope once as artifact-anchored facts with concrete boundaries, such as "The artifact ships adapters for named platforms", rather than promising that the artifact "supports" a platform.

## Durability and evidence

Deliverables contain durable guidance for readers, not a transcript of the research process.

- Do not use bookkeeping tokens or session narration such as `VERIFIED`, `HYPOTHESIS`, or `Unverified:`. Omit research-session mechanics such as fetch fallbacks and review history.
- Express uncertainty with plain-language hedges. Keep caveats durable and reader-facing. State the criterion for inferred or evaluative claims, or hedge them, rather than asserting them without support.
- Avoid durable claims that depend on external changes unless a repository artifact anchors them. Omit volatile external facts unless the facts are load-bearing; prefer category statements with descriptive Markdown links to live sources, and anchor load-bearing volatile facts to repository artifacts or pinned snapshots.

## Review judgment-bearing edits

Cross-cutting edits require local judgment at every occurrence.

- Edit one occurrence at a time and review each hunk before continuing. Do not use bulk find-and-replace for judgment-bearing edits.
