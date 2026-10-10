# ARR Responsible NLP Research Checklist draft

Draft answers for the October 2026 ARR submission form. Transfer these into OpenReview after the final PDF is frozen and update section labels if pagination or appendix lettering changes.

## A. For every submission

### A1. Did you describe the limitations of your work?

**Yes.** See the unnumbered **Limitations** section. It discusses scope and external validity, evaluator dependence, limits on component attribution, and the non-causal nature of the execution analyses.

### A2. Did you discuss any potential risks of your work?

**Yes.** See the unnumbered **Ethical considerations** section. It discusses misuse for persuasive or misleading text, unsupported claims and inherited biases, high-stakes overreliance, the need for human verification and domain-appropriate safeguards, and additional compute from multi-step execution.

### A3. Do the abstract and introduction summarize the paper's main claims?

**Yes.** See the **Abstract** and **Section 1 (Introduction)**. They summarize the process-level control formulation, the Agentic CogWriter architecture, the evaluation setup, the main pairwise findings, the ablation interpretation, and the process-trace result.

## B. Did you use or create scientific artifacts?

**Yes.** We use benchmark datasets, hosted language models, a coding-agent-style harness, and experiment code/prompts.

### B1. Did you cite the creators of artifacts you used?

**Yes.** See **Section 4 (Experimental Design), especially Benchmarks and Prompts and Implementation**, and **Appendix A (Prompt and Experiment Configuration)**. WritingBench, HelloBench, DoLoMiTes, the Habermas Machine data used in the exploratory appendix analysis, the generator/judge models, and relevant agent-system interfaces are cited where used. Source versions for the benchmark artifacts are pinned in the experiment provenance record.

### B2. Did you discuss the license or terms for use and/or distribution of any artifacts?

**Yes.** See **Appendix A, Artifact provenance and terms**. The study uses pinned WritingBench material under Apache-2.0, HelloBench under MIT, DoLoMiTes benchmark materials under CC BY 4.0, and Habermas Machine materials under CC BY 4.0. The experiment provenance record also stores source commits or archives, hashes, transformation notes, and redistribution policy.

### B3. Did you discuss whether your use of existing artifacts was consistent with their intended use?

**Yes.** See **Appendix A, Artifact provenance and terms**. The artifacts are used only for research evaluation under their released terms. We redistribute only the derived prompt manifests described by the provenance record rather than hidden reference outputs or additional source data.

### B4. Did you discuss steps taken to check whether the data contains identifying or offensive content and steps taken to protect/anonymize it?

**No.** We did not conduct an independent PII/offensive-content audit of the source benchmarks. This is stated explicitly in **Appendix A, Artifact provenance and terms**. For the Habermas Machine exploratory tasks, our materialized prompts omit source participant identifiers, but we do not claim that this constitutes a comprehensive privacy or offensive-content audit of the original artifacts.

### B5. Did you provide documentation of the artifacts, including domains/languages/phenomena/demographic groups where relevant?

**Yes, for the properties relevant to this study.** See **Section 4, Benchmarks and Prompts**, which describes the writing-task coverage of the three primary benchmarks, and **Appendix A**, which documents the pinned sources, selection procedure, and artifact provenance. We do not make claims about demographic representativeness of these benchmarks.

### B6. Did you report relevant statistics such as the number of examples and data splits?

**Yes.** See **Appendix A, Prompt selection and provenance** and **Sample size and inferential sensitivity**. We report 100 scored prompts per primary benchmark (300 total), the deterministic selection rule, exclusion of development/debug prompts, and the relevant source split for DoLoMiTes. The exploratory Habermas Machine analysis reports its 10-task sample separately.

## C. Did you run computational experiments?

**Yes.**

### C1. Did you report model parameter counts, total computational budget, and computing infrastructure?

**No, not in the provider-side form requested by the checklist.** See **Appendix B (Runtime Configuration), Compute reporting**. The generator and judges are hosted closed models; their parameter counts and provider-side accelerator configurations are not disclosed to us, so we cannot report parameter counts or GPU-hours. We instead report observable model identifiers/roles, reasoning effort, output-token budget, retry policy, token accounting where available, and wall-clock statistics recorded by the harness. No model weights are trained or fine-tuned in this study.

### C2. Did you discuss the experimental setup, including hyperparameter search and best-found values?

**Yes.** See **Section 4 (Experimental Design)** and **Appendix B (Runtime Configuration)**. We report the frozen operational settings and explicitly state that the reported reasoning effort, output-token budget, seed/retry settings, and three-run design were not selected by a documented tuning sweep. Generator temperature is reported as unset because the scored interface did not expose it.

### C3. Did you report descriptive statistics about results and make clear whether results come from a single run, mean, etc.?

**Yes.** See **Section 5 (Results)** and the run-level/sensitivity appendices. The paper distinguishes single-run analyses from three-generation-run results, reports W/L/T outcomes and win rates, uses Wilson intervals for pairwise estimates, and uses prompt-level bootstrap intervals where described.

### C4. If you used existing packages, did you report the implementation/model/parameter settings used?

**No, not exhaustively in the manuscript.** The paper reports the model/runtime settings and the experiment implementation at the level needed for the reported comparisons, while the repository lockfiles and experiment configuration pin software dependencies and source versions. The manuscript does not enumerate every transitive package/version. If an anonymized software supplement is uploaded, this answer can additionally point to that supplement.

## D. Did you use human annotators or conduct research with human participants?

**N/A for new data collection in this study.** We recruited no human annotators or participants and collected no new personal data. We reuse published benchmark artifacts under their released terms. The exploratory Habermas Machine artifact contains previously collected participant opinions; our study does not re-contact participants or conduct a new human-subject experiment.

Questions D1-D5 are therefore **N/A** for our own data collection/annotation protocol.

## E. Did you use AI assistants in research, coding, or writing?

### E1. If you used AI assistants, did you include information about your use?

**Yes.** AI assistants were used for coding and manuscript editing support, including drafting/refining code and prose under human direction. Human authors reviewed and approved the resulting changes, verified citations and experimental claims, and retain responsibility for the work. No AI system is listed as an author.

## Final-form checks before copying into OpenReview

- Replace appendix letters/section numbers if the final manuscript structure changes.
- If an anonymized software supplement is uploaded, update C4 to point to it explicitly.
- If provider-side parameter counts or compute/infrastructure information becomes available before submission, update C1 rather than retaining the current justification.
- Keep the E1 disclosure aligned with the actual tools and scope of AI assistance used by the authors.
