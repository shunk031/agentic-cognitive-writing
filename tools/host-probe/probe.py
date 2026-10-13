#!/usr/bin/env python3
"""Run the host probe on Codex or Claude Code, then check it from harness records.

Usage:
  probe.py codex DIR --codex-config PATH [--auth-command NAME --auth-env VAR]
  probe.py claude DIR [--claude-credentials PATH] [--foreground]
  probe.py check DIR

A run creates DIR, builds a fresh workspace in it, runs the host CLI in the
experiment Docker image, keeps every harness record under DIR, and prints the
check table. `check` re-reads an existing DIR. The checks read only harness
records and workspace files, never what the model says about itself.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = "agentic-cognitive-writing-experiment:local"
HOME = "/home/cog-writer-agent"
PARENT = "PPARENT-31f7"  # appears only in the probe-parent skill
CHILD = "PCHILD-8d2e"  # appears only in the probe-child skill
PROMPT = "PROMPT-5c19"  # appears only in the user prompt
USER_PROMPT = f"Session note: {PROMPT}. Keep this note to yourself."
PROXY = ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"]
PROXY += [p.lower() for p in PROXY]


def docker_base(out: Path) -> list[str]:
    args = ["docker", "run", "--rm", "--init", "--user", f"{os.getuid()}:{os.getgid()}"]
    args += ["--workdir", "/workspace", "--env", f"HOME={HOME}"]
    args += ["--mount", f"type=bind,src={out / 'workspace'},dst=/workspace"]
    for name in PROXY:
        if name in os.environ:
            args += ["--env", name]
    return args


def run(args: list[str], out: Path) -> None:
    with (
        open(out / "events.jsonl", "w") as stdout,
        open(out / "stderr.log", "w") as stderr,
    ):
        subprocess.run(args, stdout=stdout, stderr=stderr, check=False, timeout=900)


def run_codex(a, out: Path) -> None:
    home = out / "codex-home"
    shutil.copytree(HERE / "skills", out / "workspace/.agents/skills")
    home.mkdir()
    shutil.copy(a.codex_config, home / "config.toml")
    args = docker_base(out) + [
        "--entrypoint",
        "codex",
        "--env",
        "CODEX_HOME=/codex-home",
    ]
    args += ["--mount", f"type=bind,src={home},dst=/codex-home"]
    stub = out / "auth-stub"
    if a.auth_command:
        # The config's auth helper does not exist in the image. The stub prints the
        # token from the named variable, which docker passes through by name only.
        stub.write_text(f'#!/bin/sh\nprintf "%s" "${a.auth_env}"\n')
        stub.chmod(0o755)
        args += ["--env", a.auth_env]
        args += [
            "--mount",
            f"type=bind,src={stub},dst=/usr/local/bin/{a.auth_command},readonly",
        ]
    args += [
        IMAGE,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    args += [
        "-c",
        'model_reasoning_effort="low"',
        "-c",
        'agents.default_subagent_reasoning_effort="low"',
    ]
    run(args + [f"$probe-parent {USER_PROMPT}"], out)
    stub.unlink(missing_ok=True)


def run_claude(a, out: Path) -> None:
    home = out / "claude-home"
    shutil.copytree(HERE / "skills", out / "workspace/.claude/skills")
    shutil.copytree(HERE / "claude-agents", out / "workspace/.claude/agents")
    home.mkdir()
    args = docker_base(out) + [
        "--entrypoint",
        "claude",
        "--mount",
        f"type=bind,src={home},dst={HOME}/.claude",
    ]
    if a.foreground:
        args += ["--env", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1"]
    creds = Path(a.claude_credentials).resolve()
    args += [
        "--mount",
        f"type=bind,src={creds},dst={HOME}/.claude/.credentials.json,readonly",
    ]
    args += [
        IMAGE,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        a.model,
    ]
    args += ["--permission-mode", "dontAsk", "--allowedTools=Read,Write,Agent,Skill"]
    run(args + [f"/probe-parent {USER_PROMPT}"], out)
    (home / ".credentials.json").unlink(missing_ok=True)  # empty bind-mount target


def jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def short(text: str, n: int = 140) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 3] + "..."


def file_result(out: Path) -> tuple[bool, str]:
    read = out / "workspace/parent-read.txt"
    content = read.read_text().strip() if read.exists() else "(missing)"
    return content == CHILD, f"workspace parent-read.txt = {content}"


def check_codex(out: Path) -> list[tuple[str, bool, str]]:
    threads = {}  # thread id -> (session_meta payload, rows)
    for path in sorted((out / "codex-home/sessions").rglob("rollout-*.jsonl")):
        rows = jsonl(path)
        meta = next(r["payload"] for r in rows if r.get("type") == "session_meta")
        threads[meta["id"]] = (meta, rows, path.read_text(errors="replace"))
    parent = next(
        t for t, (m, _, _) in threads.items() if m.get("thread_source") == "user"
    )
    children = [
        t for t, (m, _, _) in threads.items() if m.get("parent_thread_id") == parent
    ]
    child = children[0] if children else None

    def items(tid, kind):
        return [
            r["payload"]
            for r in threads[tid][1]
            if r.get("payload", {}).get("type") == kind
        ]

    def injected(tid, name):
        for p in items(tid, "message"):
            for c in p.get("content", []):
                m = re.search(
                    rf"<skill>\s*<name>{name}</name>\s*<path>([^<]+)</path>",
                    c.get("text", ""),
                )
                if p.get("role") == "user" and m:
                    return m.group(1)
        return None

    def writes(tid):
        return sorted(
            {
                path
                for p in items(tid, "patch_apply_end")
                for path in p.get("changes", {})
            }
        )

    def calls(tid):
        names = []
        for p in items(tid, "custom_tool_call") + items(tid, "function_call"):
            body = p.get("input") or p.get("arguments") or ""
            names += re.findall(r"tools\.(\w+)\(", body) or [p.get("name")]
        return names

    rows = []
    dev = " ".join(
        c.get("text", "")
        for p in items(parent, "message")
        if p.get("role") == "developer"
        for c in p.get("content", [])
    )
    listed = [
        s
        for s in ("probe-parent", "probe-child")
        if re.search(rf"- {s}: .*\.agents/skills/{s}/SKILL\.md", dev)
    ]
    ppath = injected(parent, "probe-parent")
    rows.append(
        (
            "1 discovery",
            len(listed) == 2 and bool(ppath),
            f"parent skills list has {listed}; `$probe-parent` injected <skill> from {ppath}",
        )
    )

    spawn = next(
        (
            c
            for c in items(parent, "custom_tool_call") + items(parent, "function_call")
            if re.search(r"spawn_agent\b\W*\(", c.get("input") or "")
            or c.get("name") == "spawn_agent"
        ),
        {},
    )
    spawn_text = spawn.get("input") or spawn.get("arguments") or ""
    cpath = injected(child, "probe-child") if child else None
    first = (
        next((p["message"] for p in items(child, "user_message")), "") if child else ""
    )
    rows.append(
        (
            "2 role skill in child",
            bool(cpath),
            f"child first message {first!r}; harness injected <skill> probe-child from {cpath}",
        )
    )

    fork_false = bool(re.search(r"fork_context\W+false", spawn_text))
    leaks = [
        m
        for m in (PARENT, PROMPT)
        if child and m in threads[child][2] and m not in spawn_text
    ]
    rows.append(
        (
            "3 context isolation",
            fork_false and child is not None and not leaks,
            f"spawn call {short(spawn_text, 130)!r}; parent/prompt markers in child rollout: {leaks or 'none'}",
        )
    )

    collab = [
        e["item"]
        for e in jsonl(out / "events.jsonl")
        if e.get("type") == "item.completed"
        and e.get("item", {}).get("type") == "collab_tool_call"
    ]
    done = {
        c["tool"]
        for c in collab
        if child in (c.get("receiver_thread_ids") or [])
        and c.get("status") == "completed"
        and (
            c["tool"] == "spawn_agent"
            or c.get("agents_states", {}).get(child, {}).get("status") == "completed"
        )
    }
    ok, evidence = file_result(out)
    rows.append(
        (
            "4 files and lifecycle",
            ok and {"spawn_agent", "wait", "close_agent"} <= done,
            f"{evidence}; completed collab calls on child: {sorted(done)}",
        )
    )

    pw, cw = writes(parent), (writes(child) if child else [])
    meta_link = (
        child is not None and threads[child][0].get("parent_thread_id") == parent
    )
    receiver = child in (spawn_text + json.dumps(collab))
    rows.append(
        (
            "5 attribution",
            meta_link
            and receiver
            and "/workspace/child.txt" in cw
            and "/workspace/parent-read.txt" in pw
            and not set(pw) & set(cw),
            (
                f"child session_meta.parent_thread_id = parent: {meta_link}; spawn receiver = child: {receiver}; "
                f"parent calls {calls(parent)} wrote {pw}; child calls {calls(child) if child else []} wrote {cw}"
            ),
        )
    )
    return rows


def check_claude(out: Path) -> list[tuple[str, bool, str]]:
    events = jsonl(out / "events.jsonl")
    project = out / "claude-home/projects/-workspace"
    session = next(project.glob("*.jsonl"))
    parent = jsonl(session)
    subs = {
        p: jsonl(p)
        for p in sorted((project / session.stem / "subagents").glob("agent-*.jsonl"))
    }
    metas = {
        p: json.loads(p.with_suffix(".meta.json").read_text())
        for p in subs
        if p.with_suffix(".meta.json").exists()
    }

    def blocks(rows, kind):
        for r in rows:
            content = (r.get("message") or {}).get("content")
            for b in (
                content
                if isinstance(content, list)
                else [{"type": "text", "text": content or ""}]
            ):
                if b.get("type") == kind:
                    yield r, b

    def skill_text(rows, name):
        for r, b in blocks(rows, "text"):
            m = re.search(
                rf"Base directory for this skill: (\S*/{name})\b", b.get("text", "")
            )
            if r.get("isMeta") and m:
                return m.group(1)
        return None

    def tool_uses(rows):
        return [b for _, b in blocks(rows, "tool_use")]

    def written(rows):
        return sorted(
            {
                b["input"].get("file_path")
                for b in tool_uses(rows)
                if b["name"] in ("Write", "Edit")
            }
        )

    rows = []
    init = next((e for e in events if e.get("subtype") == "init"), {})
    seen = [s for s in ("probe-parent", "probe-child") if s in init.get("skills", [])]
    ppath = skill_text(parent, "probe-parent")
    agent_ok = "probe-child" in init.get("agents", [])
    rows.append(
        (
            "1 discovery",
            len(seen) == 2 and agent_ok and bool(ppath),
            (
                f"init skills has {seen}, init agents has probe-child: {agent_ok}; "
                f"`/probe-parent` injected skill from {ppath} (isMeta user message)"
            ),
        )
    )

    spawn = next((b for b in tool_uses(parent) if b["name"] in ("Agent", "Task")), None)
    child_path = next(
        (p for p, m in metas.items() if spawn and m.get("toolUseId") == spawn["id"]),
        None,
    )
    child = subs.get(child_path, [])
    cpath = skill_text(child, "probe-child")
    first = next(
        (
            b["text"]
            for r, b in blocks(child, "text")
            if r.get("type") == "user" and not r.get("isMeta")
        ),
        "",
    )
    rows.append(
        (
            "2 role skill in child",
            bool(cpath),
            (
                f"spawn {spawn and spawn['input']}; child first message {first!r}; "
                f"skills: preload injected {cpath} (isMeta user message)"
            ),
        )
    )

    raw = child_path.read_text() if child_path else ""
    leaks = [m for m in (PARENT, PROMPT) if m in raw and m not in json.dumps(spawn)]
    rows.append(
        (
            "3 context isolation",
            bool(child_path) and not leaks,
            (
                f"parent/prompt markers in child transcript: {leaks or 'none'} "
                "(transcripts omit the system prompt)"
            ),
        )
    )

    ok, evidence = file_result(out)
    status = [
        e.get("patch", {}).get("status") or e.get("status")
        for e in events
        if e.get("subtype") in ("task_updated", "task_notification")
    ]
    result = next(
        (
            r.get("toolUseResult")
            for r in parent
            if isinstance(r.get("toolUseResult"), dict)
            and r["toolUseResult"].get("agentId")
        ),
        {},
    )
    mode = "background" if result.get("isAsync") else "foreground"
    finished = "completed" in status or result.get("status") == "completed"
    rows.append(
        (
            "4 files and lifecycle",
            ok and finished,
            f"{evidence}; Agent ran in {mode}; task status events {status}; Agent result status {result.get('status')}",
        )
    )

    meta = metas.get(child_path, {})
    pw, cw = written(parent), written(child)
    linked = (
        bool(spawn)
        and meta.get("toolUseId") == spawn["id"]
        and result.get("agentId") in child_path.name
    )
    sidechain = all(r.get("isSidechain") for r in child if "isSidechain" in r)
    rows.append(
        (
            "5 attribution",
            linked
            and sidechain
            and "/workspace/child.txt" in cw
            and "/workspace/parent-read.txt" in pw
            and not set(pw) & set(cw),
            (
                f"subagent meta {meta}; agentId {result.get('agentId')}; child rows isSidechain: {sidechain}; "
                f"parent tools {[b['name'] for b in tool_uses(parent)]} wrote {pw}; "
                f"child tools {[b['name'] for b in tool_uses(child)]} wrote {cw}"
            ),
        )
    )
    return rows


def check(out: Path) -> bool:
    host = (out / "host").read_text().strip()
    try:
        rows = {"codex": check_codex, "claude": check_claude}[host](out)
    except (StopIteration, FileNotFoundError) as e:
        print(f"{host}: records incomplete ({e!r}); see {out}/stderr.log")
        return False
    print(f"| {host} check | result | evidence |\n| --- | --- | --- |")
    for name, ok, evidence in rows:
        print(f"| {name} | {'PASS' if ok else 'FAIL'} | {evidence.replace('|', '/')} |")
    return all(ok for _, ok, _ in rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("host", choices=["codex", "claude", "check"])
    p.add_argument("dir")
    p.add_argument("--codex-config", default=os.path.expanduser("~/.codex/config.toml"))
    p.add_argument("--auth-command")
    p.add_argument("--auth-env")
    p.add_argument(
        "--claude-credentials",
        default=os.path.expanduser("~/.claude/.credentials.json"),
    )
    p.add_argument("--model", default="claude-haiku-4-5-20251001")
    p.add_argument(
        "--foreground",
        action="store_true",
        help="Claude Code: disable background subagents",
    )
    a = p.parse_args()
    if bool(a.auth_command) != bool(a.auth_env):
        p.error("--auth-command and --auth-env go together")
    out = Path(a.dir).resolve()
    if a.host != "check":
        (out / "workspace").mkdir(parents=True)
        (out / "host").write_text(a.host)
        {"codex": run_codex, "claude": run_claude}[a.host](a, out)
    sys.exit(0 if check(out) else 1)


if __name__ == "__main__":
    main()
