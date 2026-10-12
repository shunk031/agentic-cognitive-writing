# Human-validation study record: Agentic CogWriter versus Staged

This record covers the `A4:A2` packet described in [`README.md`](./README.md). The packet, its selection rule, and its scoring are fixed. The author completes the bracketed fields.

**Packet.** 15 blinded `A4:A2` pairs from generation run 1, 5 per benchmark, drawn with seed 20260908 under the pre-specified rule in [`README.md`](./README.md). Each annotator receives one HTML page. The author keeps [`key.csv`](./key.csv) and does not send it to annotators.

**Instruction text.** Each page opens with the English and Japanese instructions, which are defined in [`human_eval_page.html`](../scripts/human_eval_page.html). Annotators:

- judge overall quality for the assignment and choose `A`, `B`, or tie
- treat a response in a language other than the assignment's as failing its language requirement
- do not prefer a response for its length alone
- work independently

The page states an estimated time of about 6.1 hours.

**Profile and consent.** Before the first pair, each page collects no name, email, or other identifying information. It asks, bilingually and as required fields, the annotator's position (undergraduate student, graduate student, researcher or faculty, or other with free text), field (natural language processing, other computer science, or other), native language (Japanese, English, Chinese, or other with free text), English reading proficiency (native or equivalent, reads English daily for work or research, or can read English with extra time), whether they can read Chinese, and whether they have experience writing long documents such as papers or reports. A consent checkbox states: "I agree that my responses will be aggregated for research and reported anonymously in a paper." The pairs stay gated behind this page until every question is answered and consent is checked; the profile answers remain editable from the final review page. The downloaded CSV repeats the profile and consent values as constant `profile_*` and `consent` columns on every row, and [`score_human_eval.py`](../scripts/score_human_eval.py) reports them per annotator in the JSON output's `profiles` block.

**Recruitment.** [AUTHOR TO COMPLETE: recruitment source, eligibility criteria, screening, relationship to the authors, and annotator count.]

**Compensation.** [AUTHOR TO COMPLETE: compensation amount or non-monetary arrangement, payment timing, and currency if applicable.]

**Consent.** [AUTHOR TO COMPLETE: consent procedure, information shown before annotation, and withdrawal procedure.]

**Data handling.** [AUTHOR TO COMPLETE: how answer files are returned, access controls, retention period, de-identification, and disposition of the optional reasons.]

**Review or ethics requirement.** [AUTHOR TO COMPLETE: institutional review, exemption, notification, or the reason no review was required, including the responsible institution or office where applicable.]

**Annotation dates.** [AUTHOR TO COMPLETE: when the pages were sent and when each answer file was returned.]

**Adjudication.** [AUTHOR TO CONFIRM: no adjudication. The analysis reports each annotator, the pooled judgments, and the majority vote.]
