"""Fidelity gate: reject runs whose harness records show a measured defect."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

from .execution import _json_objects
from .manifest import LANGUAGES

ROLES = ("planning", "translating", "reviewing")
THREAD_LIMIT_ERROR = "agent thread limit reached"
_ROLE_TOKEN = re.compile(r"\$(planning|translating|reviewing)\b")
_SKILL_ROOT = re.compile(r"(?m)^- `r\d+` = `([^`]+)`$")
# An absolute path, not the tail of a relative or variable-prefixed one.
_ABSOLUTE_SKILL_FILE = re.compile(r"(?<![\w.~$}-])/[^\s\"'`\\]*/SKILL\.md")
_SKILL_FILE_TOKEN = re.compile(r"[^\s\"'`\\]*SKILL\.md")
_PARENT_SEGMENT = re.compile(r"(?:^|[^\w.])\.\.(?:/|$)")
_CALL_TYPES = frozenset({"function_call", "custom_tool_call", "local_shell_call"})
_OUTPUT_TYPES = frozenset({"function_call_output", "custom_tool_call_output"})
_COMMAND = re.compile(r"""\bcmd"?\s*:\s*(["'`])((?:(?!\1)[^\\]|\\.)*)\1""")
# apply_patch text names the files it writes and reads nothing.
_PATCH = re.compile(r"\*\*\* Begin Patch.*?(?:\*\*\* End Patch|$)", re.S)
TRACKED_FILES = ("goals.md", "draft.md")
_HARMLESS_REDIRECT = re.compile(r"\d*>\s*/dev/null|\d*>&\d")
_HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)(\w+)\1([^\n]*)\n(?:(?:.*?\n)??[ \t]*\2[ \t]*(?=\n|$)|.*)", re.S
)
_TOKEN = re.compile(
    r"""(?P<op>\$\(|[;&|()<>`\n]+)"""
    r"""|(?P<word>(?:'[^']*'|"(?:[^"\\]|\\.)*"|\\.|[^\s;&|()<>`'"\\])+|['"\\])"""
)
_QUOTED = re.compile(r"""'([^']*)'|"((?:[^"\\]|\\.)*)"|\\(.)""")
# Bundled switches such as `-0pi`; `-M`, `-I`, and `-x` take the rest of the token.
_INPLACE = re.compile(r"-(?![MIx])\w*i|--in-place")
# A whole-word variable, alone or as an operand such as `of=$f`.
_VARIABLE = re.compile(r"(?:^|=)\$\{?\w+\}?$")
_INLINE_CODE = re.compile(r"-\w*[ceE]|-")
_CODE_WRITE = re.compile(
    r"""\bopen\w*\s*\([^\n]*?['"](?:(?:[wax][bt+]*|r[bt]*\+[bt+]*)['"]|\+?>)"""
    r"""|\.(?:write_text|write_bytes|unlink|touch)\s*\(|\bFile\.write\s*\("""
    r"""|\b(?:write|append)File\w*\s*\(|\bos\.(?:remove|rename)\s*\("""
    r"""|\bshutil\.move\s*\("""
)
_SKIPPED_WORDS = frozenset(
    {"sudo", "env", "command", "nohup", "time", "xargs", "exec", "{", "!"}
    | {"do", "then", "else", "if", "while", "until"}
)
_PATH_WRITERS = frozenset({"mv", "rm", "touch", "truncate", "sponge", "ed", "tee"})


def _script(char: str) -> str | None:
    if not char.isalpha():
        return None
    name = unicodedata.name(char, "")
    if name.startswith(("LATIN", "FULLWIDTH LATIN")):
        return "LATIN"
    if name.startswith("CJK"):
        return "CJK"
    return None


def check_output_language(text: str, language: str) -> dict[str, Any]:
    """Flag a deliverable whose dominant script is not the prompt's.

    A Latin word (a maximal run of Latin letters) and a CJK character each count
    as one unit, so English terms in Chinese prose do not outweigh it. Text with
    neither, or a tie, has no dominant script and no flag. The flag is recorded,
    never a rejection reason.
    """

    units: Counter[str] = Counter()
    previous = None
    for char in text:
        script = _script(char)
        if script == "CJK" or (script == "LATIN" and previous != "LATIN"):
            units[script] += 1
        previous = script
    ranked = units.most_common()
    dominant = (
        ranked[0][0]
        if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1])
        else None
    )
    expected = LANGUAGES[language][1]
    return {
        "expected_language": language,
        "expected_script": expected,
        "latin_words": units["LATIN"],
        "cjk_characters": units["CJK"],
        "dominant_script": dominant,
        "dominant_share": (
            round(units[dominant] / units.total(), 4) if dominant else None
        ),
        "mismatch": dominant != expected if dominant else None,
    }


def check_fidelity(
    run_dir: Path,
    *,
    platform: str,
    codex_home: Path | None,
    requires_draft: bool,
    monitor_writes_history_only: bool,
    stage_files: Sequence[str] = (),
) -> dict[str, Any]:
    """Classify a finished run as scorable or rejected, with every reason.

    ``codex_home`` is the run's own Codex home. When given, every skill root that
    Codex listed must lie inside it, and every skill file read by absolute path
    inside it or the run's workspace; records from other harnesses pass ``None``.
    ``stage_files``, when given, are workspace files the top-level thread writes
    once each, in that order, by patch only.
    """

    if platform == "codex":
        reasons = _codex_reasons(run_dir, monitor_writes_history_only, stage_files)
        if codex_home is not None:
            reasons.extend(_skill_isolation_reasons(run_dir, codex_home))
    else:
        reasons = [
            f"{platform} records expose no subagent or tool events, "
            "so fidelity cannot be verified"
        ]
    if requires_draft:
        draft = run_dir / "workspace" / ".writing" / "draft.md"
        output = run_dir / "output.normalized.txt"
        if not (
            draft.is_file()
            and output.is_file()
            and draft.read_bytes() == output.read_bytes()
        ):
            reasons.append("scored output is not workspace/.writing/draft.md")
    return {"status": "rejected" if reasons else "scorable", "reasons": reasons}


def _commands(payload: dict[str, Any]) -> list[str]:
    kind = payload.get("type")
    if kind == "custom_tool_call":
        commands = []
        for quote, text in _COMMAND.findall(str(payload.get("input", ""))):
            try:
                commands.append(json.loads(f'"{text}"') if quote == '"' else text)
            except json.JSONDecodeError:
                commands.append(text)
        return commands
    if kind == "function_call":
        try:
            arguments = json.loads(payload.get("arguments") or "{}")
        except json.JSONDecodeError:
            return []
        command = arguments.get("cmd") or arguments.get("command")
    elif kind == "local_shell_call":
        command = (payload.get("action") or {}).get("command")
    else:
        return []
    if isinstance(command, list):
        command = " ".join(map(str, command))
    return [command] if isinstance(command, str) else []


@cache
def _tracked_patterns(
    names: tuple[str, ...],
) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """Return the path-argument and anywhere-in-text patterns for tracked files.

    A path argument is tracked when it is a named file, bare or anywhere under
    `.writing`, `.writing` itself, or a glob directly under it.
    """

    files = "|".join(map(re.escape, names))
    path = re.compile(
        rf"(?:^|=|(?:^|[/=])\.writing/(?:[^/]+/)*)(?:{files})$"
        r"|(?:^|[/=])\.writing(?:/?|/[^/]*[*?\[{][^/]*)$"
    )
    text = re.compile(rf"\b(?:{files})\b|\.writing(?:/\S*[*?\[]|/?(?=[\s'\"`;|&)]|$))")
    return path, text


def _simple_command_writes(
    words: list[str],
    heredocs: str,
    tracked: Callable[[str], bool],
    names: tuple[str, ...],
) -> bool:
    """Return whether one simple command writes a tracked path."""

    while words and (words[0] in _SKIPPED_WORDS or re.match(r"\w+=", words[0])):
        words = words[1:]
    if not words:
        return False
    name, args = PurePosixPath(words[0]).name, words[1:]
    options = [arg for arg in args if arg.startswith("-")]
    paths = [arg for arg in args if tracked(arg)]
    if name in ("bash", "sh", "zsh"):
        flag = next((k for k, arg in enumerate(args) if re.match(r"-\w*c", arg)), -1)
        return flag >= 0 and _writes_tracked(" ".join(args[flag + 1 :]), names)
    if name == "git":
        rest = args
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
        sub, rest = (rest[0], rest[1:]) if rest else ("", [])
        if sub == "stash":
            return rest[:1] not in (["list"], ["show"])
        return (
            (sub == "reset" and "--hard" in rest)
            or sub == "apply"
            or (sub in ("checkout", "restore") and bool(paths))
        )
    if name == "patch":
        return bool(paths) or any(re.match(r"-p\d", option) for option in options)
    if name in ("cp", "install"):
        target = args[args.index("-t") + 1 :] if "-t" in args else args[-1:]
        return any(map(tracked, target[:1]))
    if name == "dd":
        return any(path.startswith("of=") for path in paths)
    if name in ("sed", "perl", "ruby") and any(map(_INPLACE.match, options)):
        return bool(paths)
    if re.fullmatch(r"python[\d.]*|perl|ruby|node", name):
        script = [arg for arg in args if not arg.startswith("-")]
        if not script or any(map(_INLINE_CODE.fullmatch, options)):
            code = " ".join(args) + "\n" + heredocs
            named = _tracked_patterns(names)[1]
            return bool(_CODE_WRITE.search(code) and named.search(code))
        # The script's code is not recorded, so a tracked argument may be written.
        return bool(paths)
    return name in _PATH_WRITERS and bool(paths)


def _writes_tracked(command: str, names: tuple[str, ...] = TRACKED_FILES) -> bool:
    """Return whether a shell command writes a tracked file or ``.writing``.

    The tracked files are ``names``, by default ``goals.md`` and ``draft.md``.

    A redirection, ``tee``, ``sponge``, ``mv``, ``rm``, ``touch``, ``truncate``,
    ``ed``, ``patch``, in-place ``sed``, ``perl``, or ``ruby``, or ``git checkout``
    or ``restore`` writes when a path argument is tracked; ``cp`` and ``install``
    when the destination is, and ``dd`` when ``of=`` is. Inline interpreter code
    writes when it names a tracked path and opens a file for writing or calls a
    write function; a script run with a tracked argument counts as a write.
    ``git reset --hard``, ``git stash`` other than ``list`` or ``show``,
    ``git apply``, and ``patch -p`` always count. A ``$variable`` target counts
    as tracked when the command names a tracked path anywhere.
    """

    # ponytail: a hand tokenizer; a path reached through a `cd` or `find -exec`, or
    # a variable when the command names no tracked path, is missed, and a bash
    # parser would close that if it matters.
    if "apply_patch" in command:
        return False
    path, named = _tracked_patterns(names)
    # A variable may hold a tracked path when the command names one anywhere.
    variables = bool(named.search(command))

    def tracked(word: str) -> bool:
        return bool(path.search(word) or (variables and _VARIABLE.search(word)))

    heredocs = "\n".join(match.group(0) for match in _HEREDOC.finditer(command))
    text = _HEREDOC.sub(lambda match: match.group(3) + "\n", command)
    text = _HARMLESS_REDIRECT.sub("", text)
    words: list[str] = []
    redirect = skip = False
    for match in _TOKEN.finditer(text):
        token = match.group("op")
        if token is None:
            word = _QUOTED.sub(
                lambda m: next(g for g in m.groups() if g is not None),
                match.group("word"),
            )
            if redirect and tracked(word):
                return True
            if not (redirect or skip):
                words.append(word)
            redirect = skip = False
            continue
        if any(char in token for char in ";|()`\n$") or "&&" in token or token == "&":
            if _simple_command_writes(words, heredocs, tracked, names):
                return True
            words = []
        redirect, skip = ">" in token, "<" in token and ">" not in token
    return _simple_command_writes(words, heredocs, tracked, names)


def unrecorded_writes(
    records: Iterable[dict[str, Any]], names: tuple[str, ...] = TRACKED_FILES
) -> list[str]:
    """Return shell commands that look like writes to the tracked files."""

    return [
        command
        for record in records
        if record.get("type") == "response_item"
        and isinstance(record.get("payload"), dict)
        for command in _commands(record["payload"])
        if _writes_tracked(command, names)
    ]


def _response_items(records: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for record in records:
        payload = record.get("payload")
        if record.get("type") == "response_item" and isinstance(payload, dict):
            yield payload


def _read_own_skill(records: list[dict[str, Any]], role: str) -> bool:
    """Return whether Codex injected the role skill or the agent read its file."""

    injected = f"<skill>\n<name>{role}</name>"
    skill_path = f"skills/{role}/SKILL.md"
    # Known limit: a forked rollout replays parent messages, so a parent's injected
    # role skill would count here; the fork check rejects such runs anyway.
    for payload in _response_items(records):
        if payload.get("type") == "message" and payload.get("role") == "user":
            for part in payload.get("content") or []:
                if isinstance(part, dict) and injected in str(part.get("text", "")):
                    return True
        elif payload.get("type") in _CALL_TYPES and skill_path in json.dumps(payload):
            return True
    return False


def read_codex_records(
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list], list[str]]:
    """Read a run's Codex event stream and rollouts.

    Returns the events, each thread's ``session_meta`` payload and remaining
    rollout records by thread id, and the names of rollouts without a
    ``session_meta`` first line.
    """

    events = [
        event
        for path in sorted(run_dir.glob("attempt-*.events.jsonl"))
        for event in _json_objects(path.read_bytes())
    ]
    metas: dict[str, dict[str, Any]] = {}
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    malformed: list[str] = []
    for path in sorted(run_dir.glob("sessions/**/rollout-*.jsonl")):
        lines = _json_objects(path.read_bytes())
        first = lines[0] if lines else {}
        meta = first.get("payload")
        if first.get("type") != "session_meta" or not isinstance(meta, dict):
            malformed.append(path.name)
            continue
        metas[str(meta.get("id"))] = meta
        records[str(meta.get("id"))].extend(lines[1:])
    return events, metas, records, malformed


def completed_items(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the completed items of a Codex event stream, in order."""

    return [
        event["item"]
        for event in events
        if event.get("type") == "item.completed" and isinstance(event.get("item"), dict)
    ]


def spawn_role(meta: dict[str, Any], prompt: str) -> str | None:
    """Return a spawned child's role from its agent type or its ``$role`` prompt."""

    role = meta.get("agent_role")
    if role in ROLES:
        return role
    match = _ROLE_TOKEN.search(prompt)
    return match.group(1) if match else None


def _codex_reasons(
    run_dir: Path, monitor_writes_history_only: bool, stage_files: Sequence[str]
) -> list[str]:
    events, metas, records, malformed = read_codex_records(run_dir)
    if not events:
        return ["no Codex event stream was recorded"]
    reasons = [f"rollout {name} does not start with session_meta" for name in malformed]

    # The events stream records only the top-level thread, which is the Monitor.
    top_level = {
        event["thread_id"]
        for event in events
        if event.get("type") == "thread.started"
        and isinstance(event.get("thread_id"), str)
    }
    if not top_level:
        reasons.append("Codex event stream has no thread.started event")
    items = completed_items(events)
    spawned: set[str] = set()
    closed: set[str] = set()
    spawn_prompts: dict[str, str] = {}
    for item in items:
        if item.get("type") != "collab_tool_call":
            continue
        receivers = item.get("receiver_thread_ids") or []
        if item.get("tool") == "spawn_agent":
            spawned.update(receivers)
            spawn_prompts.update(dict.fromkeys(receivers, str(item.get("prompt"))))
        elif item.get("tool") == "close_agent" and item.get("status") == "completed":
            closed.update(receivers)

    for thread in sorted((top_level | spawned) - metas.keys()):
        reasons.append(f"no rollout was recorded for thread {thread}")

    for thread, meta in sorted(metas.items()):
        if meta.get("forked_from_id"):
            reasons.append(f"child {thread} was spawned with inherited context")
        if meta.get("parent_thread_id"):
            role = spawn_role(meta, spawn_prompts.get(thread, ""))
            if role and not _read_own_skill(records[thread], role):
                reasons.append(f"{role} agent {thread} did not read its own SKILL.md")

    if monitor_writes_history_only:
        # Only apply_patch writes become file_change items, so the Monitor's shell
        # commands go through the textual write detector.
        for thread in sorted(top_level & records.keys()):
            for command in unrecorded_writes(records[thread]):
                reasons.append(f"Monitor ran shell write {command!r}")
        for item in items:
            if item.get("type") != "file_change" or item.get("status") != "completed":
                continue
            for change in item.get("changes") or []:
                path = str(change.get("path", ""))
                if PurePosixPath(path).parts[-2:] != (".writing", "history.md"):
                    reasons.append(f"Monitor wrote {path}")

    if stage_files:
        stages = [PurePosixPath(stage).parts for stage in stage_files]
        written = [
            "/".join(stage)
            for item in items
            if item.get("type") == "file_change" and item.get("status") == "completed"
            for change in item.get("changes") or []
            for stage in stages
            if PurePosixPath(str(change.get("path", ""))).parts[-len(stage) :] == stage
        ]
        if written != list(stage_files):
            reasons.append(f"stage writes were {written}, not {list(stage_files)}")
        names = tuple(dict.fromkeys(stage[-1] for stage in stages))
        for thread in sorted(records):
            for command in unrecorded_writes(records[thread], names):
                reasons.append(f"thread {thread} ran shell write {command!r}")

    # Closing a child also closes its descendants, so top-level closes suffice.
    for thread in sorted(spawned - closed):
        reasons.append(f"child {thread} was never closed")
    for thread in sorted(records):
        if any(
            payload.get("type") in _OUTPUT_TYPES
            and THREAD_LIMIT_ERROR in json.dumps(payload)
            for payload in _response_items(records[thread])
        ):
            reasons.append(f"thread {thread} hit the agent thread limit")
    return list(dict.fromkeys(reasons))


def _skill_isolation_reasons(run_dir: Path, codex_home: Path) -> list[str]:
    """Reject skill roots or skill reads outside the run's staged skills."""

    def inside(path: str, *roots: Path) -> bool:
        return any(Path(os.path.normpath(path)).is_relative_to(r) for r in roots)

    reasons: list[str] = []
    for path in sorted(run_dir.glob("sessions/**/rollout-*.jsonl")):
        lines = _json_objects(path.read_bytes())
        meta = lines[0].get("payload") if lines else None
        thread = meta.get("id") if isinstance(meta, dict) else path.name
        outputs = {
            payload.get("call_id"): json.dumps(payload)
            for payload in _response_items(lines)
            if payload.get("type") in _OUTPUT_TYPES and payload.get("call_id")
        }
        for payload in _response_items(lines):
            if payload.get("type") == "message":
                for part in payload.get("content") or []:
                    text = str(part.get("text", "")) if isinstance(part, dict) else ""
                    for root in _SKILL_ROOT.findall(text):
                        if not inside(root, codex_home):
                            reasons.append(
                                f"thread {thread} lists skill root {root} "
                                "outside the run's Codex home"
                            )
            elif payload.get("type") in _CALL_TYPES:
                # Known limit: a relative path without a `..` segment passes even
                # after a `cd` out of the workspace, as in `cd /x && cat SKILL.md`.
                text = _PATCH.sub(" ", json.dumps(payload).replace("\\n", " "))
                # A read of a path that does not exist reads nothing.
                missing = outputs.get(payload.get("call_id"), "")
                for read in _ABSOLUTE_SKILL_FILE.findall(text):
                    if re.search(
                        r"(?:^|[\s:'\"])"
                        + re.escape(read)
                        + r": No such file or directory",
                        missing,
                    ):
                        continue
                    if not inside(read, codex_home, run_dir / "workspace"):
                        reasons.append(
                            f"thread {thread} read {read} outside the staged skills"
                        )
                for read in _SKILL_FILE_TOKEN.findall(text):
                    if _PARENT_SEGMENT.search(read):
                        reasons.append(
                            f"thread {thread} read {read} through a parent directory"
                        )
    return list(dict.fromkeys(reasons))
