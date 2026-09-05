<!--
Agentic CogWriter WritingBench-native pointwise judge prompt
Version: writingbench-native-v1
Upstream source path: X-PLUG/WritingBench/benchmark_query/benchmark_all.jsonl
Upstream source commit: 9c24bb67fd7451a2eacf5810aa7721e3a8b3bdad
Native checklist blob: e6cd82aabed6fa845f0a28cd2114daad59c012b9
Upstream critic source: writingbench-prompt.py, sha256:d4d9273bbf037752871056c39e3404a8e900fe8b380c795949b111f67a2e2133
Upstream user template: user_template.txt, sha256:6eb2f31c4e6e9043eadc68e266b49140282f2150cb689d9c403a7b94c7c91413
Upstream system line: You are an expert evaluator with extensive experience in evaluating response of given query.
Cache adaptation: query and response precede the checklist; the reordered text is content-identical to the upstream critic template.
-->
Evaluate the Response based on the Query and criteria provided.

** Query **
```{query}```

** Response **
```{response}```

Provide your evaluation based on the criteria:

Provide reasons for each score, indicating where and why any strengths or deficiencies occur within the Response. Reference specific passages or elements from the text to support your justification.
Ensure that each reason is concrete, with explicit references to the text that aligns with the criteria requirements.

** Criteria **
```{criteria}```

Provide your evaluation based on the criteria:

```{criteria}```

Scoring Range: Assign an integer score between 1 to 10

** Output format **
Return the results in the following JSON format, Only output this JSON format and nothing else:
```json
{{
    "score": an integer score between 1 to 10,
    "reason": "Specific and detailed justification for the score using text elements."
}}
```
