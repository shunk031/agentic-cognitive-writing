<!--
Agentic CogWriter goal-faithfulness judge prompt
Version: goal-faithfulness-v1
-->

Assess each active goal against the final text. Mark each goal `satisfied`, `partially`, or `not`, and copy a short exact supporting quote from the final text. Judge only the displayed goals and final text.

Return exactly one JSON object and one assessment for every goal ID. Do not add assessments for other goals.

Prompt ID: {prompt_id}

Active goals: {goals}

Final text: {output}

Return this JSON shape: {{
  "prompt_id": "{prompt_id}",
  "assessments": [
    {{"goal_id": "G0", "rating": "satisfied", "supporting_quote": "<exact quote from the final text>"}} ] }}
