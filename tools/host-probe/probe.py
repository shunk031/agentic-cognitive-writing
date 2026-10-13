"""Check the host mechanics that CogWriter role agents rely on, from harness records.

Usage: python tools/host-probe/probe.py OUT [codex] [claude]

Per host (default: both), runs `probe-parent` once in the experiments/docker/ image
with a fresh workspace and harness records under OUT/HOST, then prints pass/fail per
check from those records alone. Codex uses $CODEX_HOME/config.toml and passes the
variables its `env_key` entries name; Claude Code uses the file run.sh mounts.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

HERE = Path(__file__).resolve().parent
IMAGE = "agentic-cognitive-writing-experiment:local"
PARENT, CHILD, PROMPT = "PPARENT-31f7", "PCHILD-8d2e", "PROMPT-5c19"
CHECKS = ["Discovery", "Child skill", "Isolation", "Files and lifecycle", "Attribution"]
PROXY = ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"]
WROTE = {"parent.txt", "parent-read.txt"}, {"child.txt"}  # parent, child


def docker(out: Path, env: list[str], mounts: list[str], cmd: str) -> None:
    env += [n for n in PROXY + [p.lower() for p in PROXY] if n in os.environ]
    mounts += [f"src={out / 'workspace'},dst=/workspace"]
    args = ["docker", "run", "--rm", "--init", f"--user={os.getuid()}:{os.getgid()}"]
    args += [f"--env={n}" for n in env] + [f"--mount=type=bind,{m}" for m in mounts]
    sigil = "$" if cmd.startswith("codex") else "/"
    task = f"{sigil}probe-parent Session note: {PROMPT}. Keep this note to yourself."
    with open(out / "events.jsonl", "w") as so, open(out / "stderr.log", "w") as se:
        run = [*args, IMAGE, *cmd.split(), task]
        subprocess.run(run, stdin=subprocess.DEVNULL, stdout=so, stderr=se, check=False)


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.startswith("{")]


def read_back(out: Path) -> bool:
    path = out / "workspace/parent-read.txt"
    return path.exists() and path.read_text().strip() == CHILD


def codex(out: Path) -> list[bool]:
    shutil.copytree(HERE / "skills", out / "workspace/.agents/skills")
    config = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    shutil.copy(config, out / "home")
    providers = tomllib.loads(config.read_text())["model_providers"].values()
    env = [p["env_key"] for p in providers if "env_key" in p] + ["CODEX_HOME=/c"]
    cmd = "codex exec --json --skip-git-repo-check"
    cmd += " --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort=low"
    docker(out, env, [f"src={out / 'home'},dst=/c"], cmd)
    rollouts = [jsonl(p) for p in (out / "home/sessions").rglob("rollout-*.jsonl")]
    threads = {r[0]["payload"]["id"]: r for r in rollouts}  # first row: session_meta
    up = {t: r[0]["payload"].get("parent_thread_id") for t, r in threads.items()}
    child, parent = next((t, p) for t, p in up.items() if p)
    ptext, ctext = json.dumps(threads[parent]), json.dumps(threads[child])

    def injected(text: str, name: str) -> bool:  # harness-inserted <skill> message
        return f"<skill>\\n<name>{name}</name>\\n<path>/workspace/.agents/" in text

    def wrote(t: str) -> set[str]:  # files changed through apply_patch
        events = [r["payload"] for r in threads[t] if r["type"] == "event_msg"]
        patches = [e["changes"] for e in events if e["type"] == "patch_apply_end"]
        return {Path(f).name for changes in patches for f in changes}

    events = jsonl(out / "events.jsonl")
    items = [e["item"] for e in events if e["type"] == "item.completed"]
    collab = [i for i in items if i["type"] == "collab_tool_call"]
    done = {c["tool"] for c in collab if c["receiver_thread_ids"] == [child]}
    return [
        "- probe-child: " in ptext and injected(ptext, "probe-parent"),
        injected(ctext, "probe-child"),
        PARENT not in ctext and PROMPT not in ctext,
        read_back(out) and {"spawn_agent", "wait", "close_agent"} <= done,
        {c["sender_thread_id"] for c in collab} == {parent}
        and (wrote(parent), wrote(child)) == WROTE,
    ]


def claude(out: Path) -> list[bool]:
    shutil.copytree(HERE / "skills", out / "workspace/.claude/skills")
    shutil.copytree(HERE / "claude-agents", out / "workspace/.claude/agents")
    dot = "/home/cog-writer-agent/.claude"
    mounts = [f"src={out / 'home'},dst={dot}"]
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    if (p := home / ".credentials.json").exists():
        mounts += [f"src={p.resolve()},dst={dot}/{p.name},readonly"]
    cmd = "claude --print --output-format stream-json --verbose --model haiku"
    cmd += " --permission-mode dontAsk --allowedTools=Read,Write,Agent,Skill"
    docker(out, ["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1"], mounts, cmd)
    (out / "home" / p.name).unlink(missing_ok=True)  # empty mount point
    init = next(e for e in jsonl(out / "events.jsonl") if e.get("subtype") == "init")
    project = out / "home/projects/-workspace"
    session = next(project.glob("*.jsonl"))
    parent = jsonl(session)
    results = [r.get("toolUseResult") or {} for r in parent]
    result = next(r for r in results if "agentId" in r)
    child_path = project / session.stem / f"subagents/agent-{result['agentId']}.jsonl"
    meta = json.loads(child_path.with_suffix(".meta.json").read_text())
    child, ctext = jsonl(child_path), child_path.read_text()

    def injected(rows: list[dict], name: str) -> bool:  # harness-inserted skill message
        return any(r.get("isMeta") and f"skills/{name}" in str(r) for r in rows)

    def tools(rows: list[dict], name: str) -> list[dict]:
        content = [r["message"]["content"] for r in rows if "message" in r]
        blocks = [b for c in content if isinstance(c, list) for b in c]
        return [b for b in blocks if b.get("name") == name]

    def wrote(rows: list[dict]) -> set[str]:
        return {Path(b["input"]["file_path"]).name for b in tools(rows, "Write")}

    spawn = next(iter(tools(parent, "Agent")))
    listed = {"probe-parent", "probe-child"} <= set(init["skills"])
    return [
        listed and "probe-child" in init["agents"] and injected(parent, "probe-parent"),
        injected(child, "probe-child"),
        PARENT not in ctext and PROMPT not in ctext,
        read_back(out) and result["status"] == "completed",
        (meta["agentType"], meta["toolUseId"]) == ("probe-child", spawn["id"])
        and all(r.get("isSidechain", True) for r in child)
        and (wrote(parent), wrote(child)) == WROTE,
    ]


def main() -> None:
    out, hosts = Path(sys.argv[1]).resolve(), sys.argv[2:] or ["codex", "claude"]
    build = f"docker build -t {IMAGE} -f experiments/docker/Dockerfile ."
    cmd = f"docker image inspect {IMAGE} >/dev/null || {build}"
    subprocess.run(cmd, shell=True, cwd=HERE.parents[1], check=True)
    results = {}
    for host in hosts:
        (out / host / "workspace").mkdir(parents=True)
        (out / host / "home").mkdir()
        try:
            results[host] = globals()[host](out / host)
        except (StopIteration, FileNotFoundError, KeyError):  # see OUT/HOST/stderr.log
            results[host] = [False] * 5
    print(f"| Check | {' | '.join(hosts)} |\n| --- |{' --- |' * len(hosts)}")
    for i, name in enumerate(CHECKS):
        cells = " | ".join("PASS" if results[h][i] else "FAIL" for h in hosts)
        print(f"| {name} | {cells} |")
    sys.exit(not all(map(all, results.values())))


if __name__ == "__main__":
    main()
