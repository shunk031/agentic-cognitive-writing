"""Check each CogWriter role skill alone in Codex against fixture inputs.

Usage: python tools/role-check/check.py OUT [planning] [translating] [reviewing]

Invokes each role (default: all three) directly with `codex exec` in the
experiments/docker/ image, once per fixture prompt and case, in a fresh workspace
whose `.writing/` holds fixture files; records go under OUT/PROMPT/ROLE. Codex uses
$CODEX_HOME/config.toml and gets the variables its `env_key` entries name. Prints a
pass/fail table; the good-draft row lists the unmet requirement IDs.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGE = "agentic-cognitive-writing-experiment:local"
PROXY = ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"]
GOAL = re.compile(r'- (G\d+(?:\.\d+)*): (.+) \| source: "(.+)"')
REVIEW = re.compile(
    r'- (G\d+(?:\.\d+)*): (met|unmet) \| evidence: "(.*)"'
    r"(?: \| kind: (local|structural) \| fix: (.+))?"
)
CELL = {True: "PASS", False: "FAIL"}
DRAFTS = ["draft", "draft-nosection", "draft-length"]


def codex(out: Path, role: str, files: dict[str, Path], message: str) -> set[str]:
    """Run one role in a fresh workspace; return the files its patches changed."""
    ws, home = out / "workspace", out / "home"
    (ws / ".writing").mkdir(parents=True)
    home.mkdir()
    for name, src in files.items():
        shutil.copy(src, ws / ".writing" / name)
    shutil.copytree(ROOT / "plugin/skills" / role, ws / ".agents/skills" / role)
    config = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    shutil.copy(config, home)
    providers = tomllib.loads(config.read_text())["model_providers"].values()
    env = [p["env_key"] for p in providers if "env_key" in p] + ["CODEX_HOME=/c"]
    env += [n for n in PROXY + [p.lower() for p in PROXY] if n in os.environ]
    args = ["docker", "run", "--rm", "--init", f"--user={os.getuid()}:{os.getgid()}"]
    args += [f"--env={n}" for n in env] + [f"--mount=type=bind,src={home},dst=/c"]
    args += [f"--mount=type=bind,src={ws},dst=/workspace", IMAGE]
    args += ["codex", "exec", "--json", "--skip-git-repo-check", "-c"]
    args += ["model_reasoning_effort=low", "--dangerously-bypass-approvals-and-sandbox"]
    with open(out / "events.jsonl", "w") as so, open(out / "stderr.log", "w") as se:
        run = [*args, f"${role} {message}"]
        subprocess.run(run, stdin=subprocess.DEVNULL, stdout=so, stderr=se, check=False)
    rollouts = home.glob("sessions/**/rollout-*.jsonl")
    rows = [json.loads(x) for p in rollouts for x in p.read_text().splitlines()]
    events = [r["payload"] for r in rows if r["type"] == "event_msg"]
    patches = [e["changes"] for e in events if e["type"] == "patch_apply_end"]
    return {Path(f).name for changes in patches for f in changes}


def read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def parses(path: Path, pattern: re.Pattern) -> list[re.Match]:
    """Matches for every non-blank line, or [] when any line fails or none exist."""
    found = [pattern.fullmatch(x) for x in read(path).splitlines() if x.strip()]
    return found if found and all(found) else []


def sections(text: str) -> list[str]:
    return [s.rstrip() for s in re.split(r"(?m)^(?=## )", text)]


def planning(out: Path, fx: Path, expect: dict) -> dict:
    codex(out, "planning", {"task.md": fx / "task.md"}, "Run your role.")
    goals = parses(out / "workspace/.writing/goals.md", GOAL)
    task, lines = read(fx / "task.md"), {m[1]: m[0].lower() for m in goals}

    def text(g: str) -> str:  # a goal line together with its parent lines
        return " ".join(v for k, v in lines.items() if f"{g}.".startswith(f"{k}."))

    def covered(keys: list[str]) -> bool:
        return any(all(k.lower() in text(g) for k in keys) for g in lines)

    quoted = bool(goals) and all(m[3] in task for m in goals)
    return {
        "Planning: source quotes verbatim": quoted,
        "Planning: constraints covered": all(map(covered, expect["constraints"])),
        "Format: goals.md": bool(goals),
    }


def translating(out: Path, fx: Path, expect: dict) -> dict:
    files = {n: fx / n for n in ("task.md", "goals.md")}
    files["draft.md"], scope = fx / "draft-nosection.md", expect["section"]
    wrote = codex(out, "translating", files, f'Scope: the section "{scope}".')
    new = sections(read(out / "workspace/.writing/draft.md"))
    added = [s for s in new if s.startswith("## ") and scope in s.splitlines()[0]]
    rest = [s for s in new if s not in added]
    only = len(added) == 1 and len(added[0].splitlines()) > 1
    only &= rest == sections(read(files["draft.md"]))
    return {
        "Translating: only the scope changed": only,
        "Translating: edited with the editing tool": wrote == {"draft.md"},
    }


def reviewing(out: Path, fx: Path, expect: dict) -> dict:
    unmet, unchanged, formatted = {}, True, True
    for case in DRAFTS:
        draft = fx / f"{case}.md"
        files = {n: fx / n for n in ("task.md", "goals.md")} | {"draft.md": draft}
        codex(out / case, "reviewing", files, "Run your role.")
        ws = out / case / "workspace/.writing"
        review = parses(ws / "review.md", REVIEW)
        marked = all((m[2] == "unmet") == bool(m[4]) for m in review)
        formatted &= bool(review) and marked
        unchanged &= read(ws / "draft.md") == read(draft)
        unmet[case] = {m[1] for m in review if m[2] == "unmet"}
    good = " ".join([str(len(unmet["draft"]))] + sorted(unmet["draft"]))
    missing = set(expect["missing"]) <= unmet["draft-nosection"]
    return {
        "Reviewing: removed section unmet": missing,
        "Reviewing: length unmet": set(expect["length"]) <= unmet["draft-length"],
        "Reviewing: unmet on good draft": good,
        "Reviewing: draft.md unchanged": unchanged,
        "Format: review.md": formatted,
    }


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    roles = sys.argv[2:] or ["planning", "translating", "reviewing"]
    build = f"docker build -t {IMAGE} -f experiments/docker/Dockerfile ."
    cmd = f"docker image inspect {IMAGE} >/dev/null || {build}"
    subprocess.run(cmd, shell=True, cwd=ROOT, check=True)
    fixtures = sorted(p for p in (HERE / "fixtures").iterdir() if p.is_dir())
    results = {fx.name: {} for fx in fixtures}
    for fx in fixtures:
        expect = json.loads((fx / "expect.json").read_text())
        for role in roles:
            results[fx.name] |= globals()[role](out / fx.name / role, fx, expect)
    print(f"| Check | {' | '.join(results)} |\n| --- |{' --- |' * len(results)}")
    for check in results[fixtures[0].name]:
        cells = [CELL.get(r[check], r[check]) for r in results.values()]
        print(f"| {check} | {' | '.join(cells)} |")
    sys.exit(any(v is False for r in results.values() for v in r.values()))


if __name__ == "__main__":
    main()
