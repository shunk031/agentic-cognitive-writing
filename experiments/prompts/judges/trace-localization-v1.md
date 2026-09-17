<!--
Agentic CogWriter trace-localization judge prompt
Version: trace-localization-v1
-->

Assess whether the named writing process anticipated, flagged, or recorded the specific deficiency cited by the pairwise judge against that condition's text.

Return exactly one JSON object. Use `anticipated` when the trace clearly records the deficiency before or during the work, `partially` when the trace records only part of it or records it without a usable decision, and `not` when the trace does not record it. Quote an exact passage from the displayed trace and name the cited deficiency. Do not quote the pairwise reason as the trace quote.

The process condition is {condition}. The condition {outcome} the pairwise comparison.

Pairwise judge reasons: {pairwise_reasons}

Full process trace: {trace}

A4 goals, when supplied: {goals}

Return this JSON shape: {{
  "prompt_id": "{prompt_id}",
  "condition": "{condition}",
  "outcome": "{outcome}",
  "rating": "anticipated",
  "trace_quote": "<exact passage from the full process trace>",
  "cited_deficiency": "<the deficiency cited by the pairwise judge against this condition>"
}}
