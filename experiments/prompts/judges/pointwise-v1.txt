# Agentic CogWriter pointwise judge prompt
# Version: pointwise-v1
# Protocol source: docs/experiments/protocol.md, Pointwise quality from two judges
# FastChat source path: fastchat/llm_judge/data/judge_prompts.jsonl
# FastChat source sha256: fd283293406d024f44c174b094ef48031d0687a4682fd3a56b29b138f80281b6
# FastChat adaptation: single-v1 neutral-judge framing only; the five-dimension rubric is protocol-defined.
Please act as an impartial judge of one writing response. Judge the response against the assignment and the supplied context. Do not reward outside research or facts that are not supported by the assignment or supplied context. Judge the response itself, not its condition label, length, or any hidden process.

Return exactly one valid JSON object. Do not use Markdown fences or add explanation outside the JSON object.
Return the literal `runtime-verified` marker for `judge_family`; the judge engine in `experiments/src/agentic_cogwriter/judges/engine.py` replaces that marker with the serving response's mapped family before the scorer writes the protocol record.

Use the five dimensions below. Return an integer from 1 to 5 for every dimension. Scores 2 and 4 are allowed when the response falls between the anchors.

| Dimension | Score 1 | Score 3 | Score 5 |
| --- | --- | --- | --- |
| Instruction fulfillment | Misses the central task or constraints. | Completes the main task but misses material requirements. | Meets the task and all material constraints. |
| Organization and global coherence | Ideas or sections do not form a usable whole. | The response is readable but has visible structural gaps. | The response has a clear structure and sustained global coherence. |
| Content adequacy and depth | Content is missing, shallow, or unusable for the task. | Content covers the main points with uneven development. | Content is sufficient, developed, and appropriately deep. |
| Style, voice, and audience fit | Style or voice conflicts with the requested audience or genre. | Style is partly suitable but inconsistent. | Voice, style, and detail fit the audience and genre throughout. |
| Factuality and constraint fidelity | The response contradicts the supplied context or violates important constraints. | Minor errors or unsupported claims remain. | Claims fit the supplied context, uncertainty is handled honestly, and constraints are obeyed. |

Copy one short exact evidence quote for each dimension from the response or supplied context. Keep every quote verbatim and no longer than needed to identify the evidence. The final dimension must be judged against the assignment and supplied context. Set judge_level_composite to 0.0 because the scorer computes composites after collecting all outputs. Put any uncertainty in uncertainties, or return an empty array.

[Prompt ID]
{prompt_id}

[Blind condition ID]
{condition_id}

[Platform]
{platform}

[Assignment]
{assignment}

[Supplied context]
{context}

[Output]
{output}

Return this JSON shape with the metadata values unchanged:
{{
  "prompt_id": "{prompt_id}",
  "condition_id": "{condition_id}",
  "platform": "{platform}",
  "judge_id": "{judge_id}",
  "judge_family": "{judge_family}",
  "scores": {{
    "instruction_fulfillment": 1,
    "organization_global_coherence": 1,
    "content_adequacy_depth": 1,
    "style_voice_audience_fit": 1,
    "factuality_constraint_fidelity": 1
  }},
  "evidence_quotes": [
    {{"dimension": "instruction_fulfillment", "quote": "<short exact quote>"}},
    {{"dimension": "organization_global_coherence", "quote": "<short exact quote>"}},
    {{"dimension": "content_adequacy_depth", "quote": "<short exact quote>"}},
    {{"dimension": "style_voice_audience_fit", "quote": "<short exact quote>"}},
    {{"dimension": "factuality_constraint_fidelity", "quote": "<short exact quote>"}}
  ],
  "judge_level_composite": 0.0,
  "uncertainties": []
}}
