#!/usr/bin/env python3
"""cw: the only write path for the CogWriter process state.

The runner stages this file at ``<workspace>/.agents/cw/cw.py`` next to
``cw.json``, which holds the arm keys (``goals``, ``order``, ``execution``) and
the output language. ``cw`` keeps ``.writing/history/`` and checks every
invariant of the method at the point of action. Every command prints its
history entry as its first output line.

Commands: ``step``, ``review`` (JSON on stdin), ``decide``, ``stop``, and
``para`` (paragraph on stdin).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
W = ROOT / ".writing"
TASK = W / "task.md"
GOALS = W / "goals.md"
DRAFT = W / "draft.md"
HIST = W / "history"
LOG = HIST / "history.jsonl"
PROCESSES = ("planning", "translating", "reviewing")
CYCLE = {"planning": "translating", "translating": "reviewing", "reviewing": "planning"}
RUNNER_OWNED = re.compile(r"^(turn-\d+-request\.md|retry-\d+)$")
TURN_REQUEST = re.compile(r"^turn-(\d+)-request\.md$")
GOAL_ID = re.compile(r"^G\d+(?:\.\d+)*$")
GOAL_LINE = re.compile(
    r"^((?:  )*)- \[(G\d+(?:\.\d+)*)\] (.+?) \| src: (\"(.+?)\"|G\d+(?:\.\d+)*)"
    r"(?: \| status: replaced by (G\d+(?:\.\d+)*))?$"
)
CAP = 4
PARA_LIMIT, PARA_WARN = 200, 120
PROHIBITIONS = (
    "Do not ask questions. Do not use external sources such as the web, URLs, or "
    "retrieval tools. Do not spawn agents. Do not run `codex`. Do not run "
    "`cw step`, `cw decide`, or `cw stop`."
)


class Refused(Exception):
    """A command that violates an invariant; nothing changes."""


def config() -> dict:
    return json.loads((HERE / "cw.json").read_text(encoding="utf-8"))


def norm(text: str) -> str:
    return " ".join(text.split())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(W).as_posix()


def thread() -> str:
    return os.environ.get("CODEX_THREAD_ID", "") or "unknown"


def step_dir(n: int) -> Path:
    return HIST / f"step-{n:02d}"


# ---- history ---------------------------------------------------------------


def entries() -> list[dict]:
    out = []
    if LOG.is_file():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and "n" in value:
                out.append(value)
    return out


def log_intact(history: list[dict]) -> bool:
    """The log ends with cw's last entry and the bytes before it are unchanged."""

    if not history:
        return not LOG.exists() or not LOG.read_bytes().strip()
    data = LOG.read_bytes()
    last = history[-1]
    size = last["size"]
    line = data[size:]
    return (
        hashlib.sha256(data[:size]).hexdigest() == last["prev"]
        and line.count(b"\n") == 1
        and line.endswith(b"\n")
        and json.loads(line) == last
    )


LATER: list[str] = []


def append(entry: dict, show: bool = True) -> dict:
    HIST.mkdir(parents=True, exist_ok=True)
    data = LOG.read_bytes() if LOG.is_file() else b""
    entry = {
        "n": len(entries()) + 1,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "thread": thread(),
        **entry,
        "size": len(data),
        "prev": hashlib.sha256(data).hexdigest(),
    }
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    line = json.dumps(entry, ensure_ascii=False)
    if show:
        print(line)
    else:
        LATER.append(line)
    return entry


def tracked() -> dict[str, str]:
    """Hashes of the files whose changes cw controls."""

    out = {rel(p): sha(p) for p in (GOALS, DRAFT) if p.is_file()}
    if HIST.is_dir():
        for path in sorted(HIST.rglob("*")):
            if not path.is_file() or path == LOG:
                continue
            if path.parent == HIST and RUNNER_OWNED.match(path.name):
                continue
            out[rel(path)] = sha(path)
    return out


def runner_markers(pattern: str) -> list[str]:
    return sorted(p.name for p in HIST.glob(pattern)) if HIST.is_dir() else []


def current_turn() -> int:
    return 1 + len(
        [n for n in runner_markers("turn-*-request.md") if TURN_REQUEST.match(n)]
    )


# ---- goals -----------------------------------------------------------------


def parse_goals(text: str) -> list[dict]:
    """Parse goals.md into goal records, raising ValueError on any defect."""

    goals: list[dict] = []
    stack: list[dict] = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        match = GOAL_LINE.match(line)
        if match is None:
            raise ValueError(f"goals.md line {number} does not match the grammar")
        depth = len(match[1]) // 2
        if depth > len(stack):
            raise ValueError(f"goals.md line {number} is indented under no parent")
        stack = stack[:depth]
        parent = stack[-1] if stack else None
        gid = match[2]
        expected = (
            re.fullmatch(re.escape(parent["id"]) + r"\.\d+", gid)
            if parent
            else re.fullmatch(r"G\d+", gid)
        )
        if not expected:
            raise ValueError(f"{gid} does not extend its parent's ID")
        goal = {
            "id": gid,
            "statement": match[3],
            "quote": match[5],
            "src_id": None if match[5] is not None else match[4],
            "replaced_by": match[6],
            "parent": parent["id"] if parent else None,
            "ancestors": [g["id"] for g in stack],
        }
        goals.append(goal)
        stack.append(goal)
    ids = [g["id"] for g in goals]
    if len(ids) != len(set(ids)):
        raise ValueError("goals.md repeats an ID")
    return goals


def sources() -> list[str]:
    """The fixed texts a requirement may quote: task.md and the turn requests."""

    requests = sorted(HIST.glob("turn-*-request.md")) if HIST.is_dir() else []
    return [read(TASK), *(read(p) for p in requests if TURN_REQUEST.match(p.name))]


def validate_goals(text: str, before: str, texts: list[str]) -> list[dict]:
    goals = parse_goals(text)
    normalized = [norm(t) for t in texts]
    ids = {g["id"] for g in goals}
    for goal in goals:
        if goal["quote"] is not None:
            if not any(norm(goal["quote"]) in t for t in normalized):
                raise ValueError(
                    f"{goal['id']}: the quoted src does not occur in task.md "
                    "or in a turn request"
                )
        elif goal["src_id"] not in goal["ancestors"]:
            raise ValueError(f"{goal['id']}: src {goal['src_id']} is not an ancestor")
        if goal["replaced_by"] and goal["replaced_by"] not in ids:
            raise ValueError(f"{goal['id']}: replaced by a goal that does not exist")
    try:
        old = {g["id"] for g in parse_goals(before)}
    except ValueError:
        old = set()
    if old - ids:
        raise ValueError(f"IDs disappeared: {', '.join(sorted(old - ids))}")
    if not goals:
        raise ValueError("goals.md has no requirement")
    return goals


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def active_goals() -> list[dict]:
    try:
        return [g for g in parse_goals(read(GOALS)) if not g["replaced_by"]]
    except ValueError:
        return []


def goal_events(before: str, after: str, accepted: set[str]) -> list[dict]:
    try:
        old = {g["id"]: g for g in parse_goals(before)}
    except ValueError:
        old = {}
    new = parse_goals(after)
    replaced = {
        g["replaced_by"]: g["id"]
        for g in new
        if g["replaced_by"] and not (old.get(g["id"]) or {}).get("replaced_by")
    }
    events = []
    for goal in new:
        base = {"goal_id": goal["id"], "parent_goal_id": goal["parent"]}
        if goal["id"] in replaced:
            source = replaced[goal["id"]]
            origin = "proposal" if source in accepted else "planner"
            events.append(
                {
                    "event_type": "goal_regenerated",
                    **base,
                    "replaced": source,
                    "origin": origin,
                }
            )
        elif goal["id"] not in old:
            events.append({"event_type": "goal_created", **base})
        elif old[goal["id"]]["statement"] != goal["statement"]:
            events.append({"event_type": "goal_developed", **base})
    return events


# ---- folded state ----------------------------------------------------------


class State:
    def __init__(self) -> None:
        self.cfg = config()
        self.history = entries()
        self.intact = log_intact(self.history)
        self.turn = current_turn()
        live = [e for e in self.history if "refused" not in e]
        self.coordinator = self.history[0]["thread"] if self.history else thread()
        self.steps = [e for e in live if e["cmd"] == "step"]
        self.closes = {e["step"]: e for e in live if e["cmd"] == "close"}
        records = [e for e in live if "record" in e]
        self.record = records[-1]["record"] if records else None
        self.seen_retries = {r for e in live for r in e.get("retries", [])}
        self.reviews = {e["step"]: e for e in live if e["cmd"] == "review"}
        self.decisions = [e for e in live if e["cmd"] == "decide"]
        self.stops = [e for e in live if e["cmd"] == "stop"]
        self.caller_flags = {
            e.get("open_step") for e in self.history if e.get("caller_violation")
        }
        self.paras = [e for e in live if e["cmd"] == "para"]

    # -- derived views

    @property
    def goals_on(self) -> bool:
        return bool(self.cfg["goals"])

    @property
    def delegated(self) -> bool:
        return self.cfg["execution"] == "delegated"

    @property
    def paragraph(self) -> bool:
        return self.cfg["execution"] == "paragraph"

    def open_step(self) -> dict | None:
        if self.steps and self.steps[-1]["step"] not in self.closes:
            return self.steps[-1]
        return None

    def turn_steps(self) -> list[dict]:
        return [s for s in self.steps if s["turn"] == self.turn]

    def ok_steps(self) -> list[dict]:
        return [
            s for s in self.turn_steps() if self.closes.get(s["step"], {}).get("ok")
        ]

    def passes(self) -> int:
        return sum(s["process"] == "reviewing" for s in self.ok_steps())

    def last_review(self) -> dict | None:
        """The review of the latest successful step, when that step is Reviewing."""

        ok = self.ok_steps()
        if ok and ok[-1]["process"] == "reviewing":
            return self.reviews.get(ok[-1]["step"])
        return None

    def latest_review(self) -> dict | None:
        """The review of the latest successful Reviewing step in any turn."""

        for step in reversed(self.steps):
            if step["process"] == "reviewing" and self.closes.get(step["step"], {}).get(
                "ok"
            ):
                return self.reviews.get(step["step"])
        return None

    def decided(self, review: dict | None) -> dict[str, dict]:
        if review is None:
            return {}
        return {
            d["goal"]: d for d in self.decisions if d["review_step"] == review["step"]
        }

    def undecided(self) -> list[str]:
        """Undecided proposals of this turn's latest review; a capped turn's lapse."""

        review = self.latest_review()
        turns = {s["step"]: s["turn"] for s in self.steps}
        if review is None or turns[review["step"]] != self.turn:
            return []
        done = self.decided(review)
        return [p["goal"] for p in review["proposals"] if p["goal"] not in done]

    def accepted_open(self) -> list[dict]:
        """Accepted proposals whose requirement is still active."""

        active = {g["id"] for g in active_goals()}
        out = []
        for d in self.decisions:
            if d["outcome"] == "accept" and d["goal"] in active:
                review = self.reviews[d["review_step"]]
                proposal = next(
                    p for p in review["proposals"] if p["goal"] == d["goal"]
                )
                out.append(proposal)
        return out

    def failure_state(self) -> tuple[dict | None, bool]:
        """Return the step that awaits its reissue, and whether a reissue failed."""

        pending, failed_out = None, False
        for step in self.turn_steps():
            close = self.closes.get(step["step"])
            if close is None:
                continue
            if close["ok"]:
                pending = None
            elif step["attempt"] == 1:
                pending = step
            else:
                failed_out = True
        return pending, failed_out

    def allowed(self, step: dict | None) -> set[str]:
        if step is None:
            return set()
        n, process = step["step"], step["process"]
        if process == "planning":
            return {f"history/step-{n:02d}/plan.md"} | (
                {"goals.md"} if step["goals"] else set()
            )
        if process == "translating" and not self.paragraph:
            return {"draft.md"}
        return set()

    def violations(self, step: dict | None) -> list[str]:
        if self.record is None:
            return [] if self.intact else ["history/history.jsonl"]
        current = tracked()
        record = self.record
        allowed = self.allowed(step)
        bad = sorted(
            p
            for p in set(record) | set(current)
            if record.get(p) != current.get(p) and p not in allowed
        )
        if not self.intact:
            bad.append("history/history.jsonl")
        return bad


# ---- closing a step --------------------------------------------------------


def restore(step: dict) -> list[str]:
    restored = []
    for target in (GOALS, DRAFT):
        snapshot = step_dir(step["step"]) / f"pre-{target.name}"
        if snapshot.is_file():
            if not target.is_file() or sha(target) != sha(snapshot):
                shutil.copyfile(snapshot, target)
                restored.append(target.name)
        elif target.exists():
            target.unlink()
            restored.append(target.name)
    return restored


def output_problem(state: State, step: dict) -> str | None:
    directory = step_dir(step["step"])
    process = step["process"]
    if process == "planning":
        if not read(directory / "plan.md").strip():
            return f"Planning wrote no {rel(directory / 'plan.md')}"
        if step["goals"]:
            try:
                validate_goals(read(GOALS), read(directory / "pre-goals.md"), sources())
            except ValueError as exc:
                return f"goals.md is invalid: {exc}"
        return None
    if process == "translating":
        before = directory / "pre-draft.md"
        if read(DRAFT) == read(before) and DRAFT.is_file() == before.is_file():
            return "Translating did not change draft.md"
        return None
    if step["step"] not in state.reviews:
        return "Reviewing submitted no review through `cw review`"
    return None


def close_open(state: State) -> State:
    """Close the open step: check it, restore it on failure, and log the result."""

    step = state.open_step()
    if step is None:
        bad = state.violations(None)
        new_retries = sorted(set(runner_markers("retry-*")) - state.seen_retries)
        if bad or new_retries:
            append(
                {
                    "cmd": "violation" if bad else "retry",
                    "paths": bad,
                    "retries": new_retries,
                    "record": tracked(),
                },
                show=False,
            )
            return State()
        return state
    reasons, detail = [], []
    bad = state.violations(step)
    if bad:
        reasons.append("allowance")
        detail.append("changed outside the allowance: " + ", ".join(bad))
    if step["step"] in state.caller_flags:
        reasons.append("caller")
        detail.append("a cw command came from the wrong thread during the step")
    problem = output_problem(state, step)
    if problem:
        reasons.append("output")
        detail.append(problem)
    new_retries = sorted(set(runner_markers("retry-*")) - state.seen_retries)
    if new_retries:
        reasons.append("retry")
        detail.append("the runner retried the attempt: " + ", ".join(new_retries))
    entry: dict = {"cmd": "close", "step": step["step"], "ok": not reasons}
    if reasons:
        entry |= {"reason": reasons[0], "reasons": reasons, "detail": "; ".join(detail)}
        entry["restored"] = restore(step)
    elif step["process"] == "planning" and step["goals"]:
        accepted = {d["goal"] for d in state.decisions if d["outcome"] == "accept"}
        for event in goal_events(
            read(step_dir(step["step"]) / "pre-goals.md"), read(GOALS), accepted
        ):
            event["step"] = step["step"]
            entry.setdefault("goal_events", []).append(event)
    entry["retries"] = new_retries
    entry["record"] = tracked()
    append(entry, show=False)
    for event in entry.get("goal_events", []):
        append({"cmd": "goal", **event}, show=False)
    return State()


# ---- commands --------------------------------------------------------------


def ledger(state: State) -> str:
    """The regeneration-proposal ledger of the latest step, when it was Reviewing."""

    steps = state.turn_steps()
    if not steps or steps[-1]["process"] != "reviewing":
        return ""
    review = state.reviews.get(steps[-1]["step"])
    if (
        not review
        or not review["proposals"]
        or not state.closes[steps[-1]["step"]]["ok"]
    ):
        return "regeneration proposals: none. "
    done = state.decided(review)
    parts = [
        f"{p['goal']} {done[p['goal']]['outcome']}ed ({done[p['goal']]['why']})"
        for p in review["proposals"]
        if p["goal"] in done
    ]
    return "regeneration proposals: " + ("; ".join(parts) or "none") + ". "


def require_coordinator(state: State, command: str) -> None:
    if thread() != state.coordinator:
        raise Refused(f"`cw {command}` is for the Monitor only", True)


def brief_text(state: State, n: int, step: dict) -> str:
    cfg = state.cfg
    process = step["process"]
    skill = ROOT / ".agents" / "skills" / process / "SKILL.md"
    lines = [
        f"# Step {n:02d}, attempt {step['attempt']}",
        "",
        f"- Nonce: {step['nonce']}",
        f"- Role: {process.capitalize()}",
        *(
            [f"- Previous attempt refused by cw: {step['reissue_reason']}"]
            if step.get("reissue_reason")
            else []
        ),
        f"- Role skill: {skill}",
        f"- Task: {TASK}",
        f"- Output language: {cfg['language']}",
        f"- Scope: {', '.join(step['scope']) if step['scope'] else 'the whole draft'}",
        f"- Draft: {DRAFT}",
    ]
    if state.goals_on:
        lines.append(f"- Requirements: {GOALS}")
        lines.append(
            "- Goal-setting: " + ("requested" if step["goals"] else "not requested")
        )
    if process == "planning":
        lines.append(f"- Plan file: {step_dir(n) / 'plan.md'}")
    if process == "translating":
        plans = [
            step_dir(s["step"]) / "plan.md"
            for s in state.steps
            if s["process"] == "planning" and state.closes.get(s["step"], {}).get("ok")
        ]
        lines.append(f"- Latest plan: {plans[-1] if plans else 'none'}")
    entry = state.latest_review()
    review = (
        json.loads(read(step_dir(entry["step"]) / "review.json")) if entry else None
    )
    verdicts = {v["goal"]: v for v in (review or {}).get("verdicts", [])}
    if state.goals_on:
        lines += ["", "## Active requirements and latest verdicts", ""]
        for goal in active_goals():
            verdict = verdicts.get(goal["id"])
            status = (
                "not yet reviewed"
                if verdict is None
                else "met"
                if verdict["met"]
                else f"unmet; fix: {verdict['fix']}"
            )
            lines.append(f"- {goal['id']} {goal['statement']} ({status})")
    if review and review["findings"]:
        lines += ["", "## Latest findings", ""]
        lines += [
            f"- {f['kind']} at {f['where']}: {f['fix']}" for f in review["findings"]
        ]
    if process == "planning" and state.goals_on:
        accepted = state.accepted_open()
        lines += ["", "## Accepted proposals", ""]
        lines += [
            f"- Replace {p['goal']} with: {p['replacement']}" for p in accepted
        ] or ["- none"]
    lines += ["", "## Rules", "", PROHIBITIONS, ""]
    return "\n".join(lines)


def cmd_step(state: State, args) -> None:
    require_coordinator(state, "step")
    state = close_open(state)
    cfg = state.cfg
    if any(s["turn"] == state.turn for s in state.stops):
        raise Refused("this turn has stopped; no further step is allowed")
    pending, failed_out = state.failure_state()
    if failed_out:
        raise Refused("a reissued step failed; only `cw stop --reason failure` remains")
    if state.passes() >= CAP:
        raise Refused(f"{CAP} Reviewing steps ended this turn; only `cw stop` remains")
    undecided = state.undecided()
    if undecided:
        raise Refused(
            "decide every proposal of the latest review first: " + ", ".join(undecided)
        )
    process, scope, goals = args.process, args.scope or [], bool(args.goals)
    if goals and not state.goals_on:
        raise Refused("this arm has no requirements; `--goals` is refused")
    if goals and process != "planning":
        raise Refused("`--goals` belongs to a Planning step")
    attempt, reissue_reason = 1, None
    if pending is not None:
        if (process, scope, goals) != (
            pending["process"],
            pending["scope"],
            pending["goals"],
        ):
            raise Refused(
                f"step {pending['step']:02d} failed; reissue it as `cw step "
                f"{pending['process']}` with the same scope and flags, or stop"
            )
        attempt = 2
        reissue_reason = state.closes[pending["step"]]["detail"]
    first = state.goals_on and state.turn == 1 and not state.turn_steps()
    if first and (process, goals) != ("planning", True):
        raise Refused("the first step must be `cw step planning --goals`")
    if cfg["order"] == "fixed" and pending is None:
        ok = state.ok_steps()
        expected = CYCLE[ok[-1]["process"]] if ok else "planning"
        if process != expected:
            raise Refused(f"fixed order: the next process is {expected}")
    if process == "translating" and not scope:
        raise Refused("Translating needs at least one `--scope` item")
    if state.goals_on:
        active = {g["id"] for g in active_goals()}
        inactive = [s for s in scope if GOAL_ID.match(s) and s not in active]
        if inactive:
            raise Refused("scope names inactive or unknown IDs: " + ", ".join(inactive))
    n = len(state.steps) + 1
    directory = step_dir(n)
    directory.mkdir(parents=True, exist_ok=False)
    for source in (GOALS, DRAFT):
        if source.is_file():
            shutil.copyfile(source, directory / f"pre-{source.name}")
    previous = state.turn_steps()
    step = {
        "cmd": "step",
        "event_type": "process_switch",
        "step": n,
        "turn": state.turn,
        "attempt": attempt,
        "nonce": secrets.token_hex(4),
        "process": process,
        "from_process": previous[-1]["process"] if previous else None,
        "to_process": process,
        "scope": scope,
        "goals": goals,
        "decision": ledger(state) + args.why,
    }
    if reissue_reason is not None:
        step["reissue_of"] = pending["step"]
        step["reissue_reason"] = reissue_reason
    (directory / "brief.md").write_text(brief_text(state, n, step), encoding="utf-8")
    brief = directory / "brief.md"
    if state.delegated:
        step["spawn"] = f"${process} Read {brief} and follow it. [{step['nonce']}]"
    step["record"] = tracked()
    append(step)
    if state.delegated:
        print(step["spawn"])
    else:
        skill = ROOT / ".agents" / "skills" / process / "SKILL.md"
        skill_text = read(skill)
        print(f"skill sha256: {hashlib.sha256(skill_text.encode()).hexdigest()}")
        print(read(brief))
        print(skill_text)


def cmd_review(state: State, args) -> None:
    step = state.open_step()
    if step is None or step["process"] != "reviewing":
        raise Refused("`cw review` runs only inside a Reviewing step")
    if state.delegated and thread() == state.coordinator:
        raise Refused(
            "in this arm the Reviewer, not the Monitor, submits the review", True
        )
    try:
        review = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        raise Refused(f"the review is not valid JSON: {exc}") from exc
    if not isinstance(review, dict) or not isinstance(review.get("findings"), list):
        raise Refused("the review needs a `findings` list")
    verdicts = review.get("verdicts", [])
    proposals = review.get("proposals", [])
    problems = []
    draft = norm(read(DRAFT))
    if state.goals_on:
        if not isinstance(verdicts, list) or not isinstance(proposals, list):
            raise Refused("`verdicts` and `proposals` must be lists")
        active = [g["id"] for g in active_goals()]
        seen = [v.get("goal") for v in verdicts if isinstance(v, dict)]
        missing = [g for g in active if g not in seen]
        if missing:
            problems.append("no verdict for " + ", ".join(missing))
        extra = [g for g in seen if g not in active]
        if extra or len(seen) != len(set(seen)) or len(seen) != len(verdicts):
            problems.append("each verdict names one active requirement exactly once")
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            if v.get("met") is True:
                evidence = norm(str(v.get("evidence") or ""))
                if not evidence or evidence not in draft:
                    problems.append(
                        f"{v.get('goal')}: met evidence is empty or not quoted "
                        "verbatim from draft.md"
                    )
            elif v.get("met") is False:
                if not str(v.get("fix") or "").strip():
                    problems.append(f"{v.get('goal')}: an unmet verdict needs a fix")
            else:
                problems.append(f"{v.get('goal')}: `met` must be true or false")
        for p in proposals:
            if not isinstance(p, dict) or p.get("goal") not in active:
                problems.append("a proposal names an inactive or unknown requirement")
            elif not str(p.get("replacement") or "").strip():
                problems.append(f"{p['goal']}: a proposal needs a replacement")
    elif verdicts or proposals:
        problems.append("this arm has no requirements; give findings only")
    for f in review["findings"]:
        if not isinstance(f, dict) or not str(f.get("fix") or "").strip():
            problems.append("every finding needs a non-empty `fix`")
        elif f.get("kind") not in ("structure", "local"):
            problems.append("a finding's `kind` is `structure` or `local`")
    if problems:
        raise Refused("; ".join(dict.fromkeys(problems)))
    clean = {
        "verdicts": verdicts if state.goals_on else [],
        "proposals": proposals if state.goals_on else [],
        "findings": review["findings"],
    }
    path = step_dir(step["step"]) / "review.json"
    path.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record = dict(state.record or {})
    record[rel(path)] = sha(path)
    append(
        {
            "cmd": "review",
            "step": step["step"],
            "met": sum(v.get("met") is True for v in clean["verdicts"]),
            "unmet": sum(v.get("met") is False for v in clean["verdicts"]),
            "findings": len(clean["findings"]),
            "proposals": clean["proposals"],
            "record": record,
        }
    )


def cmd_decide(state: State, args) -> None:
    require_coordinator(state, "decide")
    state = close_open(state)
    review = state.latest_review()
    goals = [p["goal"] for p in (review or {}).get("proposals", [])]
    if args.goal not in goals:
        raise Refused(f"the latest review has no proposal for {args.goal}")
    if args.goal in state.decided(review):
        raise Refused(f"the proposal for {args.goal} is already decided")
    append(
        {
            "cmd": "decide",
            "review_step": review["step"],
            "goal": args.goal,
            "outcome": args.outcome,
            "why": args.why,
            "record": tracked(),
        }
    )


def cmd_stop(state: State, args) -> None:
    require_coordinator(state, "stop")
    state = close_open(state)
    if any(s["turn"] == state.turn for s in state.stops):
        raise Refused("this turn has already stopped")
    _, failed_out = state.failure_state()
    reason = args.reason
    if reason == "failure":
        if not failed_out:
            raise Refused("`--reason failure` follows only a failed reissue")
    elif reason == "met":
        undecided = state.undecided()
        if undecided:
            raise Refused("decide every proposal first: " + ", ".join(undecided))
    if reason == "cap" and state.passes() < CAP:
        raise Refused(f"`--reason cap` needs {CAP} Reviewing steps in this turn")
    if reason == "met":
        review = state.last_review()
        if review is None:
            raise Refused("`--reason met` needs a successful Reviewing step last")
        if review["findings"]:
            raise Refused("the latest review lists findings")
        if state.goals_on:
            if not active_goals():
                raise Refused("there is no active requirement")
            if review["unmet"] or not review["met"]:
                raise Refused("the latest review has unmet requirements")
            done = state.decided(review)
            if any(done[p["goal"]]["outcome"] != "reject" for p in review["proposals"]):
                raise Refused("an accepted proposal is not yet applied")
    final = W / "history" / "final" / f"turn-{state.turn:02d}"
    final.mkdir(parents=True, exist_ok=True)
    if DRAFT.is_file():
        shutil.copyfile(DRAFT, final / "draft.md")
    previous = state.turn_steps()
    closes = [state.closes[s["step"]] for s in previous if s["step"] in state.closes]
    failed = [c for c in closes if not c["ok"]]
    append(
        {
            "cmd": "stop",
            "event_type": "process_switch",
            "turn": state.turn,
            "reason": reason,
            "failure": failed[-1]["reason"] if reason == "failure" else None,
            "from_process": previous[-1]["process"] if previous else None,
            "to_process": None,
            "decision": ledger(state) + args.why,
            "draft": "copied" if DRAFT.is_file() else "absent",
            "undecided_proposals": state.undecided(),
            "record": tracked(),
        }
    )


def cmd_para(state: State, args) -> None:
    require_coordinator(state, "para")
    step = state.open_step()
    if not state.paragraph:
        raise Refused("this arm has no paragraph unit")
    if step is None or step["process"] != "translating":
        raise Refused("`cw para` runs only inside a Translating step")
    if any(p["step"] == step["step"] for p in state.paras):
        raise Refused("this Translating step already wrote its paragraph")
    text = sys.stdin.read().strip("\n").rstrip()
    if not text.strip():
        raise Refused("the paragraph is empty")
    if re.search(r"\n[ \t]*\n", text):
        raise Refused("write one paragraph, with no blank line inside it")
    words = len(text.split())
    if words > PARA_LIMIT:
        raise Refused(f"the paragraph has {words} words; the limit is {PARA_LIMIT}")
    body = read(DRAFT).strip()
    paragraphs = [p for p in re.split(r"\n[ \t]*\n", body) if p.strip()] if body else []
    if args.replace_last:
        if not paragraphs:
            raise Refused("there is no paragraph to replace")
        paragraphs[-1] = text
    else:
        paragraphs.append(text)
    DRAFT.write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
    record = dict(state.record or {})
    record["draft.md"] = sha(DRAFT)
    entry = {
        "cmd": "para",
        "step": step["step"],
        "action": "replace-last" if args.replace_last else "append",
        "words": words,
        "record": record,
    }
    if words > PARA_WARN:
        entry["warning"] = f"the paragraph has more than {PARA_WARN} words"
    append(entry)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cw", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    step = sub.add_parser("step")
    step.add_argument("process", choices=PROCESSES)
    step.add_argument("--scope", nargs="+", action="extend")
    step.add_argument("--goals", action="store_true")
    step.add_argument("--why", required=True)
    sub.add_parser("review")
    decide = sub.add_parser("decide")
    decide.add_argument("goal")
    decide.add_argument("outcome", choices=("accept", "reject"))
    decide.add_argument("--why", required=True)
    stop = sub.add_parser("stop")
    stop.add_argument("--reason", required=True, choices=("met", "cap", "failure"))
    stop.add_argument("--why", required=True)
    para = sub.add_parser("para")
    where = para.add_mutually_exclusive_group(required=True)
    where.add_argument("--append", action="store_true")
    where.add_argument("--replace-last", action="store_true")
    args = parser.parse_args(argv)
    state = State()
    try:
        return run(args, state)
    finally:
        # Entries of steps closed on the way follow the command's own output.
        for line in LATER:
            print(line)
        LATER.clear()


def run(args, state: State) -> int:
    try:
        {
            "step": cmd_step,
            "review": cmd_review,
            "decide": cmd_decide,
            "stop": cmd_stop,
            "para": cmd_para,
        }[args.cmd](state, args)
    except Refused as exc:
        message = exc.args[0]
        entry = {"cmd": args.cmd, "refused": message}
        open_step = State().open_step()
        if len(exc.args) > 1 and open_step is not None:
            entry |= {"caller_violation": True, "open_step": open_step["step"]}
        append(entry)
        print(f"refused: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
