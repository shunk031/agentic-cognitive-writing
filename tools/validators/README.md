# Skill validators

These copies are used by CI and by the acceptance checks for every skill under `plugin/skills/`.

- `anthropic-quick_validate.py` comes from https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/scripts/quick_validate.py
- `openai-quick_validate.py` comes from https://raw.githubusercontent.com/openai/skills/main/skills/.system/skill-creator/scripts/quick_validate.py

Refresh each file from its upstream URL when the validator contract changes, then run both validators against every skill directory.
