# Repository writing guidance

## Repository scope

The repository contains a cross-platform writing plugin, baseline skill packages, research surveys, experiment protocols and code, and paper manuscripts.

The writing contract covers those artifacts and every prose deliverable, including documents, READMEs, and pull request bodies.

### Paper manuscripts

Paper manuscripts use venue-register prose. Scholarly citations use only the footnote apparatus, without bibliography-duplicating inline links; repository links appear only in an artifact-availability paragraph. This system's product and host-platform names appear once as artifact-anchored facts; cited external systems are unaffected.

## Citations and links

Published works use complete footnotes, while resource pointers use descriptive Markdown links; markers identify every cited entity without needless repetition.

### Published works

- Attach each GitHub-flavored footnote marker, `[^n]`, directly after the named entity at first mention and at any load-bearing mention. Keep footnote markers outside emphasis spans, as in `**Name**[^n]`, not `**Name [^n]**`. Define the marker with authors or organization, title, venue, year, and a DOI, arXiv, or ACL URL. Keep footnote definitions at the end of the file without a manual heading such as `## Footnotes` or `## References`.
- Use one marker per entity per unit, where a unit is a paragraph, table row, or contiguous list. Re-mark an entity in a distant load-bearing section with the same number when needed.
- Give sibling names sharing one footnote a single group marker, and give every cited entity at least one marker somewhere in the document.
- Do not add a labeled `Paper:` entry that duplicates a marker already attached to the entity in the same passage.

### Resource links

- Use inline descriptive Markdown links for resource pointers, including repositories, code or data files, docs pages, dataset cards, and licenses. A name may carry both its footnote marker and nearby resource links. Leave a URL bare only when its literal string is what readers must copy or type, such as in a command, an endpoint, or a DOI identifier in a bibliography entry.
- Write short runs of two to four links inline with slash separators only when labels are brief, such as `[Repo](url) / [data](url) / [eval prompt](url)`. Use a colon lead-in followed by one link per bullet for runs whose labels are long file paths, and keep those links out of prose parentheticals. Keep slash-separated runs flat, without parenthesized sub-runs or labeled sub-groups; use lead-ins with sub-bullets for grouped sources with internal structure.
- For longer same-entity link runs or labels needing qualifiers, except runs whose labels are long file paths, name the shared entity once in a lead-in; the lead-in carries the entity's footnote marker when the entity is a published work, and otherwise uses a descriptive label or link. Follow the lead-in with a few sub-bullets. Give each sub-bullet a category label and an inline slash-separated run, and do not put a single resource link on each line.
- For in-repository links, use repo-relative paths computed from the mentioning file's location for living references. Commit-pinned in-repository URLs are forbidden unless the pinned commit is on the default branch's history and the snapshot is genuinely load-bearing; external-repository pins are unaffected. Never use branch-qualified URLs such as `blob/<branch>/...`, because a branch name is a movable pointer that can be deleted or rewritten, while a repository-relative path, or a URL pinned to a commit on the default branch's history, stays resolvable. Commit identifiers appear only inside link URLs as pinned snapshot targets under descriptive labels; prose never contains a commit hash and states the design as a current fact.
- Writers compute repo-relative links from the mentioning file's location when turning bare in-repository file-path mentions into code-formatted relative Markdown links, such as [`AGENTS.md`](./AGENTS.md). Writers keep runtime or user-environment paths, ground-truth tokens, and copyable command paths as plain text.

## Structure and formatting

Writers format content for reader use: facts go in tables, reasoning in prose, and actions in bullets; headings, first sentences, and tables expose the main answer and top caveats in a 30-second skim.

### Lists and prose

- Use bullets for separate decisions, claims, steps, or multi-word structure.
- Match the format to the content rather than forcing every point into a list.
- Format `Monitor`, `Planning`, `Translating`, and `Reviewing` as code when prose names them as system processes or roles. Leave identifiers, ordinary-English uses, and direct quotations unchanged.
- Present sibling entities within one section in parallel forms. When primary entries use labeled bold-lead-in bullets, give secondary entries the same form scaled to their weight; never collapse them into a single fact-only paragraph.
- Keep short atomic-token reference lists inline regardless of count. When an exact enumeration is not load-bearing, summarize it with a source link, but never summarize away content that is the claim, such as exact schema keys. Summarize third-party procedures in prose with a descriptive source link; use step lists only for procedures the reader executes. Keep two-item enumerations in prose when a list adds no value.
- Within a scope, omit an established name from children under a lead-in, cells after a row header, and sentences inside an entity's own section. Labels carry only the differentiating part.
- Open each paragraph with a topic sentence stating its one point. Keep following sentences on that point, start a new paragraph for a new point, and make the first sentences alone carry the full argument. A definition or gloss belongs in the sentence that uses the term or in its own explicitly declared paragraph, never as a trailing sentence in a paragraph about another point. Merge runs of single-sentence paragraphs created by list-to-prose conversion, and use blank lines only for genuine topic shifts.
- Use bold lead-ins ending with a period for labeled prose groups, as in **Label.** New detail ..., rather than "Label:" pseudo-headers. Keep colons for genuine lists and examples.
- Fragment bullets take no trailing period; sentence bullets are punctuated. Keep each list internally consistent.

### Tables

- Use tables for atomic, comparable values. When a table cell must hold several entries, separate them with `<br>` because bullet lists do not render inside cells. When a cell needs sentences or more than about two `<br>`-separated lines, move the content to per-item subsections or prose and keep at most a compact table of atomic-value summaries. Right-align only purely numeric columns and left-align text columns.
- In comparison tables, keep each entity's brief resource links in a `Resources` column as slash-separated links so each row holds the entity's facts and links together; the two-to-four limit does not apply inside `Resources` cells, but labels remain brief. Keep detail sections to links tied to a specific claim.

### Headings and sections

- Use sentence-case headings and no manual section numbers. Refer to sections by name or link.
- Open each major section with its takeaway.

### README files

README files present only the mainstream installation or usage path inline and link a dedicated document that holds the alternatives. Each fact and procedure appears once at its best location.

## Language and claim strength

Writers produce all prose deliverables in English and remove AI-pattern phrasing, puffery, and filler from each deliverable; apply the `unslop` skill where available.

- Introduce an abbreviation only when the document uses it again; otherwise keep the full form without a parenthetical. Expand a reused abbreviation at first use. Leave universally understood tokens such as URL, JSON, HTTP, PDF, API, CLI, README, and DOI, as well as proper names and brands such as JSTOR, arXiv, and GitHub, unexpanded.
- Avoid pronoun subjects such as "It", "This", and "They" unless the referent is the immediately preceding subject and unambiguous. Name the actor instead, as in "The survey derives ..." or "The monitor appends ...".
- Describe an artifact by its function, not with self-assessed size or effort qualifiers such as "small", "thin", "simple", or "lightweight". State platform, support, and compatibility scope once as artifact-anchored facts with concrete boundaries, such as "The artifact ships adapters for named platforms", rather than promising that the artifact "supports" a platform.

## Durability and evidence

Deliverables contain durable guidance for readers, not a transcript of the research process.

- Do not use bookkeeping tokens or session narration such as `VERIFIED`, `HYPOTHESIS`, or `Unverified:`. Omit research-session mechanics such as fetch fallbacks and review history.
- Express uncertainty with plain-language hedges. Keep caveats durable and reader-facing. State the criterion for inferred or evaluative claims, or hedge them, rather than asserting them without support.
- Avoid durable claims that depend on external changes unless a repository artifact anchors them. Omit volatile external facts unless the facts are load-bearing; prefer category statements with descriptive Markdown links to live sources, and anchor load-bearing volatile facts to repository artifacts or pinned snapshots.
- Public repository artifacts never reference non-public repositories, internal hostnames, private mount paths, or private-repository URLs. When a private source must be acknowledged, write an unlinked plain-text provenance note carrying no repository name, path, or commit identifier.

## Review judgment-bearing edits

Cross-cutting edits require local judgment at every occurrence.

- Edit one occurrence at a time and review each hunk before continuing. Do not use bulk find-and-replace for judgment-bearing edits.
- When a defect or unnecessary passage is flagged in a deliverable, treat it as an instance of a class: survey the whole deliverable and sibling deliverables that can carry the class, fix every instance, and report found and fixed counts. Never fix only the quoted spot.
