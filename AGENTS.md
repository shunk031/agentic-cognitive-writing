# Repository writing guidance

This repository hosts the following artifact types:

- a cross-platform writing plugin;
- research surveys;
- an experiment protocol.

These rules apply across every artifact type above. Write all prose deliverables in English, including:

- docs;
- READMEs;
- PR bodies.

## Citations and links

- A reference to a published work, such as a paper or book, is a citation. Format it as a GitHub-flavored Markdown footnote marker, `[^n]`. Its definition must carry:
  - the authors;
  - the title;
  - the venue;
  - the year;
  - one of these work URLs:
    - a DOI URL;
    - an arXiv URL;
    - an ACL URL.
- Attach the marker directly after the named entity at first mention and wherever the name is load-bearing. Reuse the same footnote. Use academic forms such as `WritingBench [^1]` and `STORM [^2]`.
- A pointer to a resource is an inline link wherever it occurs. Resource pointers include:
  - repositories;
  - code or data files;
  - docs pages;
  - dataset cards;
  - licenses.
- A name may carry both its citation marker and nearby inline resource links.

## Prose and editing

- English prose follows the `unslop` skill. Do not restate that skill here.
- For judgment-bearing cross-cutting edits, classify each occurrence and edit one occurrence at a time. Review each hunk before continuing. Do not use bulk find-and-replace.
- Format parallel enumerations of three or more items as CommonMark bulleted lists. Keep two-item enumerations in prose when a list would add noise.
