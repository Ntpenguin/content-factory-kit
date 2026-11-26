"""Write new scripts: a background Claude run drafts a new batch, then the copy checks decide.

    python -m factory.write <brand> <customer> <count>   a new batch folder, the writer, the checks
    python -m factory.write --check <brand> <batch>      the copy checks only (nothing is rendered)
    python -m factory.write --selfcheck

The writer is `claude -p` in restricted mode with five file tools: no Bash, no connectors, no web. It may
write five named files inside the new batch folder and nothing else. It runs on the Claude plan this laptop is signed in to
and spends no generation credits. What it writes is a draft: the checks here are the same ones the render
lanes run, and nothing is rendered, voiced, posted or sent.
"""
import json
import re
import shutil
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path

from factory.brand import ROOT, BrandError, load_brand
from factory.gate import check_piece, check_video
from factory.hooks import check_hooks, load_evidence
from factory import hooks as hook_sheet

RUNS = ROOT / "runs"
COUNTS = (5, 10, 20)                    # hooks in one run; the dashboard offers exactly these
WRITER_MODEL = "opus"                   # spares the Fable window; the checks below catch what it gets wrong
TOOLS = ("Read", "Glob", "Grep", "Write", "Edit")
FIX_ROUNDS = 3                          # times the checks' findings go back to the writer
ROUND_SECONDS = 20 * 60                 # one writer round; past this its process is stopped
FILES = ("hooks.json", "statics.json", "videos.json")
WRITES = FILES + ("evidence.md", "notes.md")      # the only files the writer may make or change
DRAFT = "not-done"                      # in the folder from the start of a run until every check passes; the writer cannot remove it
KEEP = WRITES + ("brief.md", DRAFT)                # all a batch folder may hold when a writer round ends


def batches(slug):
    """The brand's batch folders that hold hooks.json and evidence.md, fullest and newest first."""
    found = [d for d in (RUNS / slug).glob("*") if (d / "hooks.json").is_file() and (d / "evidence.md").is_file()]
    return sorted(found, key=lambda d: (sum((d / f).is_file() for f in FILES), d.name), reverse=True)


def new_batch(slug, today=None):
    """Make runs/<brand>/<date>-scripts (or -scripts-2, -3 ...) and return it. Reuses only a stopped run's leftover: a folder with nothing but the brief and the copied evidence."""
    stem = f"{today or date.today().isoformat()}-scripts"
    for n in range(1, 100):
        folder = RUNS / slug / (stem if n == 1 else f"{stem}-{n}")
        try:
            folder.mkdir(parents=True)
            return folder
        except FileExistsError:
            if folder.is_dir() and {p.name for p in folder.iterdir()} <= {"brief.md", "evidence.md", DRAFT}:
                return folder
    raise BrandError(f"{RUNS / slug} already has 99 script batches for {stem}")


def example_for(slug):
    """The first batch that passes the copy checks. A writer's batch still marked not-done (stopped, or problems left) never counts:
    the plain check cannot see what that run did to its evidence lines."""
    return next((d for d in batches(slug) if not (d / DRAFT).exists() and not check(slug, d.name)), None)


def brief(slug, customer, count, folder, example):
    brand = load_brand(slug)
    callouts = brand["brand"].get("audience_callouts", [])
    rel = lambda p: p.relative_to(ROOT).as_posix()
    who = (f'Every hook\'s "customer" is exactly "{customer}".' if customer != "all" else
           f'Spread the hooks across these customers: {", ".join(callouts)}. A hook that fits all of them takes "all".')
    return f"""You are the script writer of the content factory in this folder. Write {count} new ad hooks for the brand `{slug}`, with the first-test static ads and short videos that go with them.

Your folder is `{rel(folder)}/`. You can write the five files named below there and nothing else; every other write is refused. You have file tools only. Nothing you write is rendered, posted or sent: these are drafts a person reviews.

## Read first, in this order
1. `CLAUDE.md` (the limits).
2. Everything in `knowledge/`: `hooks.md` (all ten sections), `formats.md`, `platforms.md`, `compliance.md`, `editing-rules.md`, `sources.md`.
3. `brands/{slug}/facts.md`, `icp.md`, `offers.md`, `brand.json`.
4. What exists already: every `runs/{slug}/*/hooks.json` (no spoken line of yours may repeat one, or reword one closely), every `runs/{slug}/*/decisions.json` if there is one (the owner's approvals, rejections and comments: write more like what he approved and nothing like what he rejected) and any file in a `results/` folder whose name does not start with SAMPLE.
5. The worked example, `{rel(example)}/`: `hooks.json`, `statics.json`, `videos.json`, `evidence.md`. Your files have the same shape.
6. The checks your files must pass: `check_hooks` in `factory/hooks.py`, `check_piece` and `check_video` in `factory/gate.py`, `check_copy` in `factory/claims.py`. Read them; they are short and exact about limits.

## Write, in your folder
- `hooks.json`: `brand`, `batch` ("{folder.name}"), `bodies`, `hooks`. Exactly {count} hooks with ids H01, H02 and so on. {who} Reuse the example's `bodies` block as it is unless a hook needs a new body; a new body cites its facts. Mark 3 to 6 hooks, your strongest and no two alike, with `"test": "<body>-<CTA>"`. Give every hook a `note` naming the formula or rule it uses and its source id, such as "Formula: promise, S15".
- `statics.json`: `brand`, `batch`, `pieces`. One static for each hook marked `test`, with the id `<hook>-<its test>`, such as H03-M2-A.
- `videos.json`: `voice` (copy the example's block), `pieces`. One video for each hook marked `test`, with the same id as its static, `"lane": "punch"`. Use spoken `say` lines only; do not use `audio`, `clip` or `image`, since you cannot hear or see a file. The first beat is the hook (`"say": "hook"`), the last is the end card.
- `evidence.md` is already there, copied from the example. Cite its ids in each hook's `evidence`. Leave its lines as they are. You may add lines in its exact format; a source id must be in `knowledge/sources.md`, a line that rests on judgment is graded [guess], and a line you add is never graded [measured].
- `notes.md`: for each hook marked `test`, two sentences: why it should stop this customer's scroll, and which knowledge section it rests on.

## Rules that decide pass or fail
- A claim is a fact in `brands/{slug}/facts.md`, cited by its id on the line that makes it. Nothing else: no result, saving, speed, price or guarantee from anywhere else, and nothing from the never-claim list.
- Every number and timeframe in a line must appear in a fact that line cites. A clock time that sets a scene ("2 AM") is fine.
- Nobody claims to be a customer, and no line is a first-person story of an experience. No named rival.
- Words that fail the check: the long dash, "it's not X, it's Y", and hype words (transform, unlock, seamless, effortless and the rest of the list in `factory/claims.py`). Write the way a tradesperson talks.
- Limits: hook on screen at most 7 words, hook spoken at most 20; the rest are in `factory/gate.py` (MAX_WORDS, MAX_CHARS, MAX_ROWS, LANES).
- Use different hook types and formulas across the {count}; do not write one idea {count} ways.

A checker runs when you stop. What fails comes back to you to fix. End with five lines or fewer: what you wrote and which hooks you marked for the first test.
"""


def _json(path, problems):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        problems.append(f"{path.name}: the top level must be an object")
    except FileNotFoundError:
        problems.append(f"{path.name} is missing")
    except (OSError, ValueError) as e:
        problems.append(f"{path.name} does not parse: {e}")
    return None


def check(slug, batch, customer=None, count=None, fresh=False):
    """Every problem in the batch's copy, as a list of lines. Empty means it passes. Renders nothing.
    fresh: a batch the writer just made. Its spoken lines must not repeat an earlier batch's, and every hook marked for the
    first test needs its static and its video (older batches share hooks and skip pieces on purpose)."""
    brand = load_brand(slug)
    folder = RUNS / slug / batch
    problems = []
    data = _json(folder / "hooks.json", problems)
    if data is None:
        return problems
    try:
        for hid, bad in check_hooks(data, brand, load_evidence(folder / "evidence.md")).items():
            problems += [f"hooks.json {hid}: {p}" for p in bad]
    except BrandError as e:
        problems.append(str(e))
    except (AttributeError, KeyError, TypeError) as e:
        return problems + [f"hooks.json has the wrong shape ({type(e).__name__}: {e}); copy the worked example's"]
    hooks = [h for h in data.get("hooks", []) if isinstance(h, dict)]
    if count is not None and len(hooks) != count:
        problems.append(f"hooks.json has {len(hooks)} hooks; {count} were asked for")
    if customer not in (None, "all"):
        problems += [f"hooks.json {h.get('id')}: customer is '{h.get('customer')}', this run is for '{customer}'" for h in hooks if h.get("customer") != customer]
    key = lambda text: re.sub(r"\W+", " ", str(text).lower()).strip()
    for other in batches(slug) if fresh else ():
        if other == folder:
            continue
        try:
            old = {key(h["spoken"]) for h in json.loads((other / "hooks.json").read_text(encoding="utf-8"))["hooks"]}
        except (OSError, ValueError, KeyError, TypeError):
            continue
        problems += [f"hooks.json {h.get('id')}: same spoken line as a hook in {other.name}" for h in hooks if key(h.get("spoken")) in old]
    if any(p.startswith("hooks.json") for p in problems):
        return problems                 # the pieces lean on the hooks; check them once the hooks hold

    want = {f"{h['id']}-{h['test']}" for h in hooks if "test" in h} if fresh else set()
    for name, checker in (("statics.json", check_piece), ("videos.json", check_video)):
        spec = _json(folder / name, problems)
        if spec is None:
            continue
        pieces = spec.get("pieces") if isinstance(spec.get("pieces"), list) else []
        seen = set()
        for piece in pieces:
            pid = str(piece.get("id")) if isinstance(piece, dict) else repr(piece)
            try:
                bad = checker(piece, data, brand)[1]
            except (AttributeError, KeyError, TypeError, ValueError) as e:
                bad = [f"wrong shape ({type(e).__name__}: {e}); copy the worked example's"]
            if pid in seen:
                bad.append("is in the file twice")
            seen.add(pid)
            problems += [f"{name} {pid}: {p}" for p in bad]
        problems += [f"{name}: no piece for {pid}, a hook marked for the first test" for pid in sorted(want - seen)]
    return problems


def added_evidence(folder, example):
    """Problems in what the writer did to evidence.md: the example's lines stay as they were, and a new line is never [measured]."""
    try:
        new, old = load_evidence(folder / "evidence.md"), load_evidence(example / "evidence.md")
    except BrandError:
        return []                       # check() reports an evidence file that does not load
    return ([f"evidence.md {k}: this line came from the example; put it back exactly as it was" for k in old if new.get(k) != old[k]]
            + [f"evidence.md {k}: a line you add is graded [claim] or [guess], never [measured]" for k in sorted(new.keys() - old.keys()) if new[k]["grade"] == "measured"])


def claude():
    home = Path.home() / ".local" / "bin" / "claude.exe"
    exe = Path(home if home.is_file() else shutil.which("claude") or home).resolve()
    if not exe.is_file() or exe.is_relative_to(ROOT):       # on Windows `which` looks in the current folder first
        raise BrandError("the `claude` command was not found outside this project; the writer needs Claude Code installed and signed in")
    return str(exe)


def command(folder, session=None):
    """The writer's command line. Everything it may do is decided here; the prompt goes in on stdin."""
    mine = [f"/{folder.relative_to(ROOT).as_posix()}/{name}" for name in WRITES]     # a leading slash: from the project folder
    cmd = [claude(), "-p", "--restricted", "--strict-mcp-config", "--model", WRITER_MODEL,
           "--tools", ",".join(TOOLS), "--permission-mode", "dontAsk",
           "--allowedTools", *(f"{tool}({path})" for path in mine for tool in ("Write", "Edit")),
           "--disallowedTools", "Read(**/.env*)", "Read(**/.git/**)",
           "--output-format", "stream-json", "--verbose"]
    return cmd + (["--resume", session] if session else [])


def _inside(target, folder):
    path = Path(target) if Path(target).is_absolute() else ROOT / target
    return path.resolve().is_relative_to(folder.resolve())


def unsettled(state, folder):
    """Writes outside the folder whose outcome the stream never showed. Any one of them stops the run."""
    return sorted(t for t in state["writes"].values() if not _inside(t, folder))


def sweep(folder):
    """Remove everything in the batch folder that is not one of KEEP, and return what was removed. The writer is refused
    such files; one that exists anyway (a page, a results file, a fake decisions.json) must not stay where the dashboard serves it."""
    extra = sorted((p for p in folder.rglob("*") if p.relative_to(folder).as_posix() not in KEEP), reverse=True)
    for p in extra:
        p.rmdir() if p.is_dir() and not p.is_symlink() else p.unlink()
    return [p.relative_to(folder).as_posix() for p in extra]


def watch(event, folder, state):
    """One line of the writer's stream -> a short line to print, or None. Raises BrandError when the run must stop.
    state carries the session id, the pending writes and the final result between lines."""
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        state["session"] = event.get("session_id")
        tools, servers = event.get("tools"), event.get("mcp_servers")
        if not (isinstance(tools, list) and tools and isinstance(servers, list)):
            raise BrandError("the writer did not say which tools and connectors it started with; stopped before it did anything")
        extra = sorted(set(map(str, tools)) - set(TOOLS))
        servers = [s.get("name", "?") if isinstance(s, dict) else str(s) for s in servers]
        if extra or servers:
            raise BrandError(f"the writer started with more than its five file tools (tools: {extra}, connectors: {servers}); stopped before it did anything")
        state["init"] = True
        return f"writer started ({event.get('model', WRITER_MODEL)}, tools: {', '.join(tools)})"
    if kind == "assistant":
        out = []
        for part in event.get("message", {}).get("content", []):
            if part.get("type") != "tool_use":
                continue
            if not state.get("init") or part.get("name") not in TOOLS:
                raise BrandError(f"the writer used the tool {part.get('name')!r} that is not one of its five, or used one before it listed them; stopped")
            arg = part.get("input", {})
            target = str(arg.get("file_path") or arg.get("pattern") or arg.get("path") or "")
            if part.get("name") in ("Write", "Edit"):
                state["writes"][part.get("id")] = target
            short = target.replace("\\", "/").removeprefix(ROOT.as_posix() + "/")
            out.append(f"  {str(part.get('name')).lower()} {short}")
        return "\n".join(out) or None
    if kind == "user":
        for part in event.get("message", {}).get("content", []):
            if not isinstance(part, dict) or part.get("type") != "tool_result":
                continue
            target = state["writes"].pop(part.get("tool_use_id"), None)
            if target is None:
                continue
            inside = _inside(target, folder)
            if not inside and not part.get("is_error"):
                raise BrandError(f"the writer wrote outside its folder: {target}. Stopped. Look at `git status` before using anything from this run")
            if not inside:
                return f"  refused, as it should be: a write to {target}"
        return None
    if kind == "result":
        state["result"] = event
    return None


def writer(prompt, folder, session=None):
    """Run one writer round. Returns its session id. Raises BrandError when it fails or breaks a limit."""
    state = {"session": session, "writes": {}, "result": None, "init": False}
    extra = []
    proc = subprocess.Popen(command(folder, session), cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    late = threading.Timer(ROUND_SECONDS, proc.kill)        # this exact process, never one found by name
    late.start()
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                print(line.rstrip()[:300], flush=True)      # not part of the stream: the CLI's own message
                continue
            if isinstance(event, dict):
                said = watch(event, folder, state)
                if said:
                    print(said, flush=True)
        code = proc.wait()
    except BrandError:
        proc.kill()
        raise
    finally:
        late.cancel()
        if proc.poll() is None:
            proc.kill()
        extra = sweep(folder)
    if extra:
        raise BrandError(f"the writer made files it was not asked for: {', '.join(extra)}. They were removed and the run stopped")
    if unsettled(state, folder):
        raise BrandError(f"the writer tried to write outside its folder and the outcome is unknown: {', '.join(unsettled(state, folder))}. Stopped. Look at `git status` before using anything from this run")
    result = state["result"] or {}
    if code != 0 or result.get("is_error") or not state["result"]:
        why = str(result.get("result") or f"it ended with code {code} and no result (a round is stopped after {ROUND_SECONDS // 60} minutes)")
        raise BrandError(f"the writer did not finish: {why[:600]}")
    if not state["session"]:
        raise BrandError("the writer gave no session id, so a fix round could not reach it")
    print("writer says: " + str(result.get("result", "")).strip()[:1200], flush=True)
    return state["session"]


def changed(folder):
    """git's view of every file outside the batch folder: a weak third look after the CLI's own refusals and watch().
    It cannot see ignored paths (tmp/, node_modules/, .env) or a second change to a file that was already modified."""
    out = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    mine = folder.relative_to(ROOT).as_posix() + "/"
    return {line for line in out.splitlines() if mine not in line}


def run(slug, customer, count):
    brand = load_brand(slug)
    if not isinstance(brand["brand"].get("audience_callouts", []), list):
        raise BrandError(f"audience_callouts in {slug}'s brand.json must be a list")
    if customer != "all" and customer not in brand["brand"].get("audience_callouts", []):
        raise BrandError(f"'{customer}' is not one of {slug}'s customers in brand.json")
    if count not in COUNTS:
        raise BrandError(f"count must be one of {', '.join(map(str, COUNTS))}")
    earlier = batches(slug)
    if not earlier:
        raise BrandError(f"{slug} has no batch with hooks.json and evidence.md yet; a session writes a brand's first batch")
    example = example_for(slug)
    if example is None:
        raise BrandError(f"none of {slug}'s batches passes the copy checks, so there is no worked example to copy. "
                         f"See `python -m factory.write --check {slug} {earlier[0].name}`")
    folder = new_batch(slug)
    (folder / DRAFT).write_text("This batch is a draft: its run was stopped or left problems. It is never the worked example for a later run.\n", encoding="utf-8")
    shutil.copyfile(example / "evidence.md", folder / "evidence.md")
    (folder / "brief.md").write_text(text := brief(slug, customer, count, folder, example), encoding="utf-8")
    where = folder.relative_to(ROOT).as_posix()
    print(f"New batch: {where}\nWriting {count} hooks for {customer} ({slug}). This takes several minutes.", flush=True)

    before = changed(folder)
    session = writer(text, folder)
    for attempt in range(FIX_ROUNDS + 1):
        problems = check(slug, folder.name, customer, count, fresh=True) + added_evidence(folder, example)
        if not problems:
            break
        print(f"\nThe checks found {len(problems)} problem(s):\n" + "\n".join(f"  - {p}" for p in problems[:60]), flush=True)
        if attempt == FIX_ROUNDS:
            break
        print(f"Sending them back to the writer (fix round {attempt + 1} of {FIX_ROUNDS}).", flush=True)
        session = writer("The checker found these problems in your files. Fix every one in your folder, changing as little else as you can, "
                         "and keep to the rules in the brief. A line that fails the claims check gets a fact it can cite or is rewritten without the claim; "
                         "never invent a fact.\n\n" + "\n".join(f"- {p}" for p in problems[:120]), folder, session)
    stray = sorted(changed(folder) - before)
    if stray:
        print("\nCHECK THIS: files outside the batch folder changed during the run (the writer is refused there, so another session may have done it):\n"
              + "\n".join(f"  {s}" for s in stray), flush=True)
    if problems:
        print(f"\nNOT DONE: {len(problems)} problem(s) are left after {FIX_ROUNDS} fix rounds. The drafts stay in {where}; they are not ready to render.")
        return False
    (folder / DRAFT).unlink()
    hook_sheet.run(slug, folder.name)
    data = json.loads((folder / "hooks.json").read_text(encoding="utf-8"))
    print(f"\nDONE: {len(data['hooks'])} hooks in {where}, every line passes the copy checks. Read them in {where}/hook-sheet.md.\nMarked for the first test:")
    for h in data["hooks"]:
        if "test" in h:
            print(f"  {h['id']} ({h['type']}, {h['customer']}): {h['spoken']}")
    print("Next: pick this batch on the Make tab and render the static ads. Videos need voice lines first, which a session makes.")
    return True


def selfcheck():
    import tempfile
    assert check("builtwithbaron", "2026-11-16-batch1") == [], check("builtwithbaron", "2026-11-16-batch1")
    assert any("7 were asked for" in p for p in check("builtwithbaron", "2026-11-16-batch1", count=7))
    assert any("this run is for 'Electricians'" in p for p in check("builtwithbaron", "2026-11-16-batch1", customer="Electricians"))
    twin = check("builtwithbaron", "2026-11-16-faceless", fresh=True)       # the same hooks as batch 1: as a new batch, every line is a repeat
    assert len(twin) >= 50 and all("same spoken line" in p for p in twin), twin[:3]

    global RUNS
    real, tmp = RUNS, Path(tempfile.mkdtemp(prefix="write-check-", dir=ROOT / "tmp"))
    try:
        RUNS = tmp
        src, dst = real / "builtwithbaron" / "2026-11-16-batch1", tmp / "builtwithbaron" / "b"
        dst.mkdir(parents=True)
        for name in FILES + ("evidence.md",):
            shutil.copyfile(src / name, dst / name)
        assert check("builtwithbaron", "b") == []
        assert example_for("builtwithbaron") == dst
        (dst / DRAFT).write_text("", encoding="utf-8")
        assert example_for("builtwithbaron") is None, "a batch still marked not-done is never the worked example"
        (dst / DRAFT).unlink()
        assert all("no piece for" in p for p in check("builtwithbaron", "b", fresh=True)) and check("builtwithbaron", "b", fresh=True)
        edit = lambda name, fn: (dst / name).write_text(json.dumps(fn(json.loads((src / name).read_text(encoding="utf-8")))), encoding="utf-8")
        cut = lambda spec: dict(spec, pieces=spec["pieces"][1:])
        edit("statics.json", cut)
        assert any(p.startswith("statics.json: no piece for") for p in check("builtwithbaron", "b", fresh=True))
        edit("statics.json", lambda s: s)
        edit("videos.json", lambda v: dict(v, pieces=v["pieces"] + [{"id": "H01-M3-A", "lane": "punch", "beats": "none"}, "junk"]))
        bad = check("builtwithbaron", "b")
        assert any("beats" in p for p in bad) and any("wrong shape" in p for p in bad), bad
        edit("videos.json", lambda v: v)

        def claim(data):
            data["hooks"][0]["spoken"] = "We answer every call in 3 seconds, guaranteed."
            return data
        edit("hooks.json", claim)
        bad = check("builtwithbaron", "b")
        assert bad and all(p.startswith("hooks.json H01") for p in bad), bad      # an invented number stops at the hooks
        (dst / "hooks.json").write_text("{not json", encoding="utf-8")
        assert "does not parse" in check("builtwithbaron", "b")[0]
        (dst / "hooks.json").unlink()
        assert check("builtwithbaron", "b") == ["hooks.json is missing"]

        for name in FILES + ("evidence.md",):
            shutil.copyfile(src / name, dst / name)
        (dst / "review.html").write_text("<script>", encoding="utf-8")
        (dst / "results").mkdir()
        (dst / "results" / "meta.csv").write_text("x", encoding="utf-8")
        assert sweep(dst) == ["review.html", "results/meta.csv", "results"], "files the writer was not asked for are removed"
        assert sorted(q.name for q in dst.iterdir()) == sorted(FILES + ("evidence.md",))
        assert added_evidence(dst, src) == []
        with (dst / "evidence.md").open("a", encoding="utf-8") as f:
            f.write("- **E90** [measured] Plumbers buy three times more. — source: S15" + chr(10) + "- **E91** [guess] A hunch. — source: S15" + chr(10))
        assert [q.split(":")[0] for q in added_evidence(dst, src)] == ["evidence.md E90"], added_evidence(dst, src)
        first = new_batch("x", "2026-01-02")
        (first / "brief.md").write_text("b", encoding="utf-8")
        (first / DRAFT).write_text("", encoding="utf-8")
        assert new_batch("x", "2026-01-02") == first, "a stopped run's leftover folder is reused"
        (first / "hooks.json").write_text("[]", encoding="utf-8")
        second = new_batch("x", "2026-01-02")
        assert (first.name, second.name) == ("2026-01-02-scripts", "2026-01-02-scripts-2"), "a folder with work in it is never reused"
    finally:
        RUNS = real
        shutil.rmtree(tmp)

    folder = RUNS / "builtwithbaron" / "2026-01-02-scripts"
    cmd = command(folder)
    assert "--restricted" in cmd and "--strict-mcp-config" in cmd and cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[cmd.index("--tools") + 1] == "Read,Glob,Grep,Write,Edit" and "Bash" not in " ".join(cmd)
    assert "Write(/runs/builtwithbaron/2026-01-02-scripts/hooks.json)" in cmd and command(folder, "abc")[-2:] == ["--resume", "abc"]
    rules = cmd[cmd.index("--allowedTools") + 1:cmd.index("--disallowedTools")]
    assert len(rules) == 2 * len(WRITES) and not any("*" in r or "brief.md" in r or ".html" in r for r in rules), rules
    assert not Path(claude()).is_relative_to(ROOT)
    state = {"session": None, "writes": {}, "result": None, "init": False}
    init = {"type": "system", "subtype": "init", "session_id": "s1", "tools": list(TOOLS), "mcp_servers": []}
    assert "writer started" in watch(init, folder, state) and state["session"] == "s1"
    for more in ({"tools": list(TOOLS) + ["Bash"]}, {"mcp_servers": [{"name": "higgsfield"}]}):
        try:
            watch(dict(init, **more), folder, state)
            raise AssertionError("a writer with extra tools or a connector must be stopped")
        except BrandError:
            pass
    for odd in ({"tools": None}, {"tools": []}, {"mcp_servers": None}):
        try:
            watch(dict(init, **odd), folder, state)
            raise AssertionError(f"a start that does not list tools and connectors must be stopped: {odd}")
        except BrandError:
            pass
    tool = lambda name: {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t0", "name": name, "input": {}}]}}
    for name, st in (("Read", dict(state, init=False)), ("Bash", state), ("mcp__higgsfield__generate_image", state)):
        try:
            watch(tool(name), folder, st)
            raise AssertionError(f"{name} before the tool list, or outside it, must stop the run")
        except BrandError:
            pass
    use = lambda path: {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Write", "input": {"file_path": path}}]}}
    done = lambda err: {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": err}]}}
    watch(use(str(folder / "hooks.json")), folder, state)
    assert watch(done(False), folder, state) is None                             # a write in its folder
    watch(use(str(ROOT / "brands" / "builtwithbaron" / "facts.md")), folder, state)
    assert "refused" in watch(done(True), folder, state)                         # a refused write outside: noted, the run goes on
    for outside in (str(ROOT / "brands" / "builtwithbaron" / "facts.md"), str(folder / ".." / "x.json"), "CLAUDE.md"):
        watch(use(outside), folder, state)
        try:
            watch(done(False), folder, state)
            raise AssertionError(f"a write outside the folder that went through must stop the run: {outside}")
        except BrandError:
            pass
    watch(use(str(ROOT / "CLAUDE.md")), folder, state)
    watch({"type": "user", "message": {"content": "no result parts"}}, folder, state)
    assert unsettled(state, folder) == [str(ROOT / "CLAUDE.md")], "a write outside with no outcome shown is still held against the run"
    text = brief("builtwithbaron", "Plumbers", 10, folder, RUNS / "builtwithbaron" / "2026-11-16-batch1")
    assert 'exactly "Plumbers"' in text and "Exactly 10 hooks" in text and "runs/builtwithbaron/2026-01-02-scripts/" in text
    assert "Electricians" in brief("builtwithbaron", "all", 5, folder, RUNS / "builtwithbaron" / "2026-11-16-batch1")
    for bad in (("builtwithbaron", "Dentists", 10), ("builtwithbaron", "Plumbers", 7)):
        try:
            run(*bad)
            raise AssertionError(f"run{bad} must be refused before anything is made")
        except BrandError:
            pass
    assert not folder.exists()
    print("write selfcheck passed")


if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        if args == ["--selfcheck"]:
            selfcheck()
        elif len(args) == 3 and args[0] == "--check":
            found = check(args[1], args[2])
            print("\n".join(found) if found else f"{args[2]}: every line passes the copy checks")
            sys.exit(1 if found else 0)
        elif len(args) == 3 and args[2].isdigit():
            sys.exit(0 if run(args[0], args[1], int(args[2])) else 1)
        else:
            sys.exit(__doc__)
    except BrandError as e:
        sys.exit(f"Stopped: {e}")
