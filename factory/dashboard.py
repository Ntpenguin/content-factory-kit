"""The dashboard: one local page for the whole factory.

    python -m factory.dashboard [--port 8790] [--allow-host NAME --allow-login EMAIL]
    python -m factory.dashboard --selfcheck

It shows the state file, every brand and batch, and every document; saves approve, reject and comments
straight into the batch's decisions.json; and runs the factory's own steps (the commands in HOWTO.md), one
at a time. It spends nothing and posts nothing: voice lines and pictures are still made by a session.

Safety: binds 127.0.0.1 only. Every request needs a local Host header, or the one Tailscale host named on
the command line together with that login in the Tailscale-User-Login header `tailscale serve` sets. A
request from another site's page is refused. Only files under SERVE_DIRS with a SERVE_EXT ending are served.
A run is one of ACTIONS, with a brand, batch and clip that exist on disk, a customer from the brand's own list and a
count from a fixed list; nothing typed reaches a command.
"""
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from factory import look, read, write
from factory.brand import BRANDS, ROOT, BrandError, load_brand

PORT = 8790
RUNS = ROOT / "runs"
PAGE = Path(__file__).with_name("dashboard.html")
SERVE_DIRS = ("runs", "brands", "knowledge", "research", "reports", "sounds")
SERVE_EXT = {".html", ".png", ".jpg", ".jpeg", ".svg", ".mp4", ".mp3", ".wav", ".md", ".json", ".csv"}
TEXT = {".md": "text/plain", ".csv": "text/plain", ".json": "application/json", ".html": "text/html"}
SELFCHECKS = [[m, "--selfcheck"] for m in ("factory.brand", "factory.hooks", "factory.video", "factory.look", "factory.footage",
                                           "factory.learn", "factory.read", "factory.write", "factory.dashboard")] + [
    ["factory.claims"], ["factory.gate"], ["checks.neg_statics"], ["checks.neg_video"], ["checks.neg_footage"], ["checks.neg_learn"]]
# id: (button, what it does, what it needs: "" | "brand" | "batch" | "clip" | "write", commands as `python -m` arguments)
ACTIONS = {
    "write": ("Write new scripts", "Claude drafts new hooks for one kind of customer, with a static ad and a short video script for the strongest few, in a new batch. Every line must pass the copy checks. About 5 to 15 minutes. It uses your Claude plan, not generation credits; nothing is rendered or posted.",
              "write", [["factory.write", "{brand}", "{customer}", "{count}"]]),
    "brand": ("Check the brand folder", "Loads brand.json, the facts, the customer profile and the offers, and refuses a broken one. A few seconds.",
              "brand", [["factory.brand", "{brand}"]]),
    "hooks": ("Build the hook sheet", "Checks every hook in hooks.json, then writes hook-sheet.md and matrix.csv. A few seconds.",
              "batch", [["factory.hooks", "{brand}", "{batch}"]]),
    "statics": ("Render the static ads", "Checks the copy in statics.json, renders each ad in 3 sizes and checks the images. About 90 seconds for 10 ads.",
                "batch", [["factory.statics", "{brand}", "{batch}"]]),
    "lines": ("List the voice lines to make", "Names every voice line videos.json needs that is not on disk yet. Making one costs credits, so a session does that.",
              "batch", [["factory.video", "{brand}", "{batch}", "--lines"]]),
    "video": ("Render the videos", "Renders videos.json in 2 sizes and checks every video. About 5 minutes for 5 videos. Look notes stop counting after a re-render.",
              "batch", [["factory.video", "{brand}", "{batch}"]]),
    "footage": ("Cut a phone clip", "Drops the silences and retakes from a clip in the batch's media/raw folder and writes the cut beside it.",
                "clip", [["factory.footage", "{brand}", "{batch}", "{clip}"]]),
    "look": ("Make the look sheets", "Six frames of every video side by side, and a list of the videos nobody has looked at.",
             "batch", [["factory.look", "{brand}", "{batch}"]]),
    "scan": ("Scan the video frames", "Checks the videos on disk, 6 frames a second, for anything outside the safe area. No re-render.",
             "batch", [["checks.scan", "{brand}", "{batch}"]]),
    "read": ("List the lines nobody has read", "Writes read-pending.json: the lines of copy a fresh reader still has to check against their facts.",
             "batch", [["factory.read", "{brand}", "{batch}"]]),
    "review": ("Rebuild the review page", "Writes review.html again from the latest checks, read verdicts and look notes. A few seconds.",
               "batch", [["factory.review", "{brand}", "{batch}"]]),
    "learn": ("Build the scoreboard", "Ranks the hooks from the results files in the batch's results folder. It needs a real results file; the sample is never mixed in.",
              "batch", [["factory.learn", "{brand}", "{batch}"]]),
    "checks": ("Run every self-check", "Runs each step's own check and the failure cases that must fail. A few minutes; it renders small test videos.",
               "", SELFCHECKS),
}
LOCK = threading.Lock()
JOB = {"id": 0, "label": "", "running": False, "stopped": "", "code": None, "started": "", "ended": "", "out": ""}   # stopped: why, when it was
PROC = None
_looks = {}
QUIET_DAYS = (6, 0, 1, 2, 3)        # Sunday to Thursday
FENCE = None                        # the Windows job object every run is put in; see fence()
if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    K32.CreateJobObjectW.restype = wintypes.HANDLE
    K32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    K32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    K32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    FENCE = K32.CreateJobObjectW(None, None)


class Refused(Exception):
    pass


def quiet_time(now=None):
    """Nate's rule: no heavy work from 16:45 to 17:10 CT, Sunday to Thursday. Runs stop 10 minutes early so none is still going at 16:45.
    ponytail: this is the laptop's clock, which is set to Central; use zoneinfo if the laptop ever travels."""
    now = now or datetime.now()
    return now.weekday() in QUIET_DAYS and (16, 35) <= (now.hour, now.minute) < (17, 10)


def until_quiet(now=None):
    """Seconds until 16:45 on a day that has the window still ahead, else None. A run still going then is stopped.
    ponytail: looks at today only; no run lasts past midnight."""
    now = now or datetime.now()
    edge = now.replace(hour=16, minute=45, second=0, microsecond=0)
    return (edge - now).total_seconds() if now.weekday() in QUIET_DAYS and now < edge else None


def fence(proc):
    """Put a run inside this server's Windows job object. Stop ends that job: exactly what the run started (python, node,
    ffmpeg) and nothing else. Not `taskkill /T`: it finds children by parent process id, Windows reuses ids, and an old
    process whose dead parent once had the run's id would be killed with it. That could be the trading bot.
    ponytail: the run joins the job a moment after it starts, before Python has loaded; create it suspended if a step ever starts children faster than that."""
    if os.name == "nt" and not (FENCE and K32.AssignProcessToJobObject(FENCE, int(proc._handle))):
        proc.kill()                     # this exact process, by the handle Popen holds: never left running where Stop could not reach it
        raise OSError(f"Windows would not fence the run (error {ctypes.get_last_error()})")


def refuse(headers, port, allow=None):
    """Why this request is refused, or None. allow is (tailscale host, login), both lower case."""
    if headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none") and headers.get("Sec-Fetch-Mode") != "navigate":
        return "requests from another site are refused"     # its <img>, <script> or fetch; a link someone follows (from Jarvis, say) is fine
    host = (headers.get("Host") or "").lower()
    if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):          # anything else may be DNS rebinding
        login = (headers.get("Tailscale-User-Login") or "").strip().lower()
        if not allow or host.split(":")[0] != allow[0] or login != allow[1]:
            return "this address is not allowed"
    origin = headers.get("Origin")
    if origin is not None and urlsplit(origin).netloc.lower() != host:   # a page on another site
        return "requests from another site are refused"
    return None


def resolve(urlpath):
    """The file a URL path may read, or None."""
    rel = unquote(urlpath).lstrip("/")
    if "\\" in rel or ":" in rel:       # a backslash or a drive makes an absolute or network path, which Windows would open before the folder check below
        return None
    parts = Path(rel).parts
    if not parts or any(p.startswith(".") for p in parts):
        return None
    path = (ROOT / rel).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file() or path.suffix.lower() not in SERVE_EXT:
        return None
    inside = path.relative_to(ROOT).parts
    if any(p.startswith(".") for p in inside):
        return None
    if len(inside) == 1:
        return path if path.suffix.lower() == ".md" else None           # the project's own documents
    return path if inside[0] in SERVE_DIRS else None


def rel(path):
    return path.relative_to(ROOT).as_posix()


def batches():
    return [(b.name, d.name) for b in sorted(RUNS.glob("*")) if b.is_dir() for d in sorted(b.glob("*")) if d.is_dir()]


def sections(text):
    """A markdown file's '## ' sections: {title: body}."""
    out, name = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            out[name] = []
        elif name:
            out[name].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def load_decisions(folder):
    path = folder / "decisions.json"
    return json.loads(path.read_text(encoding="utf-8")).get("decisions", {}) if path.is_file() else {}


def save_decision(slug, batch, piece, decision=None, comment=None):
    """Approve, reject or comment on one piece, in the file factory.learn reads (the review page's Export format)."""
    if (slug, batch) not in batches():
        raise Refused(f"no batch {slug}/{batch}")
    folder = RUNS / slug / batch
    gate = folder / "gate.json"
    if not gate.is_file() or piece not in json.loads(gate.read_text(encoding="utf-8"))["pieces"]:
        raise Refused(f"no piece {piece!r} in {slug}/{batch}")
    if decision not in (None, "", "approve", "reject"):
        raise Refused("a decision is approve, reject or empty")
    if comment is not None and (not isinstance(comment, str) or len(comment) > 2000):
        raise Refused("a comment is text of at most 2,000 characters")
    with LOCK:
        done = load_decisions(folder)
        old = done.get(piece, {})
        done[piece] = {"decision": old.get("decision", "") if decision is None else decision,
                       "comment": old.get("comment", "") if comment is None else comment,
                       "at": datetime.now().isoformat(timespec="seconds")}
        tmp = folder / "decisions.json.tmp"
        tmp.write_text(json.dumps({"batch": f"{slug}:{batch}", "decisions": done}, indent=1, ensure_ascii=False), encoding="utf-8")
        for _ in range(5):
            try:
                os.replace(tmp, folder / "decisions.json")
                break
            except PermissionError:     # Windows refuses while the file is open, as it is for the instant a page reads it
                time.sleep(0.05)
        else:
            tmp.unlink(missing_ok=True)
            raise Refused("decisions.json is open in another program, so nothing was saved; close it and try again")
    return done[piece]


def look_note(folder, pid, files):
    """look.note hashes every video; remember the answer until a file or look.json changes."""
    lj = folder / "look.json"
    stamp = (str(folder), pid, lj.stat().st_mtime_ns if lj.is_file() else 0,
             tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in files.values()))
    if stamp not in _looks:
        _looks[stamp] = look.note(folder, pid, files)
    return _looks[stamp]


def brand_state(slug):
    d = BRANDS / slug
    docs = [rel(p) for p in sorted(d.glob("*.md"))]
    try:
        b = load_brand(slug)
    except BrandError as err:
        return {"slug": slug, "name": slug, "error": str(err), "docs": docs, "facts": None}
    j = b["brand"]
    return {"slug": slug, "name": j["name"], "site": j["site"], "tagline": j.get("tagline", ""), "colors": j["colors"],
            "look": j.get("look", ""), "voice": j.get("voice", []), "ctas": j["ctas"], "callouts": j.get("audience_callouts", []),
            "logo": f"brands/{slug}/{j['logos'].get('lockup') or next(iter(j['logos'].values()), '')}",
            "facts": [{"id": i, **f} for i, f in b["facts"].items()], "never": len(b["never"]), "docs": docs}


def batch_state(slug, batch, facts):
    folder = RUNS / slug / batch
    has = lambda name: (folder / name).is_file()
    load = lambda name: json.loads((folder / name).read_text(encoding="utf-8"))
    hooks = {h["id"]: h for h in load("hooks.json")["hooks"]} if has("hooks.json") else {}
    gate = load("gate.json") if has("gate.json") else {"pieces": {}}
    decisions = load_decisions(folder)
    pieces = []
    for pid, p in gate["pieces"].items():
        on_disk = {n: folder / r for n, r in p["files"].items() if (folder / r).is_file()}
        mp4s = {n: f for n, f in on_disk.items() if f.suffix == ".mp4"}
        hook, said = hooks.get(pid.split("-")[0], {}), decisions.get(pid, {})
        pieces.append({"id": pid, "kind": p["kind"], "problems": p["problems"], "seconds": p.get("seconds"), "notes": p.get("notes", []),
                       "files": {n: rel(f) for n, f in on_disk.items()}, "missing": len(p["files"]) - len(on_disk),
                       "hook": hook.get("spoken", ""), "customer": hook.get("customer", ""), "type": hook.get("type", ""),
                       "look": look_note(folder, pid, mp4s) if mp4s else None,
                       "decision": said.get("decision", ""), "comment": said.get("comment", "")})
    reads = None
    if gate["pieces"] and facts is not None:
        todo, done = read.lines(folder, facts), read.saved(folder)
        reads = {"lines": len(todo), "flagged": sum(k in done and not done[k]["ok"] for k in todo),
                 "unread": sum(k not in done for k in todo), "bare": sum(not v["facts"] for v in todo.values())}
    raw = folder / "media" / "raw"
    made = bool(pieces) and not any(p["missing"] for p in pieces)
    stations = [("Brief", has("brief.md"), "brief.md"), ("Customer", (BRANDS / slug / "icp.md").is_file(), "the brand's icp.md"),
                ("Evidence", has("evidence.md"), "evidence.md"), ("Hooks", has("hooks.json"), "hooks.json"),
                ("Scripts", has("statics.json") or has("videos.json"), "statics.json or videos.json"),
                ("Production", made, "rendered files for every piece"),
                ("Gate and review", has("gate.json") and has("review.html"), "gate.json and review.html"),
                ("Learn", has("scoreboard.md"), "scoreboard.md from real results")]
    return {"brand": slug, "batch": batch, "checked": gate.get("checked", ""), "pieces": pieces, "hooks": len(hooks), "reads": reads,
            "review": rel(folder / "review.html") if has("review.html") else None,
            "docs": [rel(p) for p in sorted(folder.glob("*.md")) + sorted(folder.glob("*.csv")) + sorted((folder / "results").glob("*.csv"))],
            "clips": sorted(p.name for p in raw.glob("*") if p.is_file()) if raw.is_dir() else [],
            "stations": [{"name": n, "done": bool(d), "needs": w} for n, d, w in stations]}


def state():
    brands = [brand_state(p.name) for p in sorted(BRANDS.glob("*")) if p.is_dir()]
    facts = {b["slug"]: {f["id"]: f for f in b["facts"]} if b["facts"] is not None else None for b in brands}
    out = []
    for slug, batch in batches():
        try:
            out.append(batch_state(slug, batch, facts.get(slug)))
        except (BrandError, ValueError, KeyError, OSError) as err:           # one broken batch must not blank the page
            out.append({"brand": slug, "batch": batch, "error": f"{type(err).__name__}: {err}", "pieces": [], "docs": [], "clips": [],
                        "stations": [], "hooks": 0, "reads": None, "review": None, "checked": ""})
    library = [("Project", sorted(ROOT.glob("*.md")))] + [(d.capitalize(), sorted((ROOT / d).glob("*.md"))) for d in ("knowledge", "research", "reports", "sounds")]
    status = ROOT / "STATUS.md"
    return {"status": sections(status.read_text(encoding="utf-8")) if status.is_file() else {}, "brands": brands, "batches": out,
            "library": [{"group": g, "docs": [rel(p) for p in ps]} for g, ps in library if ps],
            "actions": [{"id": k, "label": v[0], "about": v[1], "needs": v[2]} for k, v in ACTIONS.items()], "quiet": quiet_time(),
            "counts": [str(c) for c in write.COUNTS]}


def start(action, slug="", batch="", clip="", customer="", count=""):
    """Start one of ACTIONS. Brand, batch and clip must be names found on disk; a customer is one of the brand's own, a count one of write.COUNTS."""
    if action not in ACTIONS:
        raise Refused(f"no action {action!r}")
    label, _, needs, commands = ACTIONS[action]
    if quiet_time():
        raise Refused("runs are off from 4:35 to 5:10 PM, Sunday to Thursday (the trading bot's window)")
    if needs in ("brand", "write") and not (slug and (BRANDS / slug).is_dir() and slug in [p.name for p in BRANDS.glob("*")]):
        raise Refused(f"no brand {slug!r}")
    if needs in ("batch", "clip") and (slug, batch) not in batches():
        raise Refused(f"no batch {slug}/{batch}")
    fill = {"brand": slug, "batch": batch}
    if needs == "write":
        try:
            known = list(load_brand(slug)["brand"].get("audience_callouts", [])) + ["all"]
        except (BrandError, TypeError) as err:
            raise Refused(str(err))
        if customer not in known:
            raise Refused(f"no customer {customer!r} in {slug}'s brand.json")
        if count not in map(str, write.COUNTS):
            raise Refused(f"a count is one of {', '.join(map(str, write.COUNTS))}")
        fill.update(customer=customer, count=count)
    if needs == "clip":
        raw = RUNS / slug / batch / "media" / "raw"
        if not raw.is_dir() or clip not in [p.name for p in raw.glob("*") if p.is_file()]:
            raise Refused(f"no clip {clip!r} in {slug}/{batch}/media/raw")
        fill["clip"] = str(raw / clip)
    commands = [[part.format(**fill) for part in cmd] for cmd in commands]
    with LOCK:
        if JOB["running"]:
            raise Refused(f"\"{JOB['label']}\" is still running: one run at a time")
        JOB.update(id=JOB["id"] + 1, label=label + (f": {slug}" if needs else "") + (f" / {batch}" if needs in ("batch", "clip") else "")
                   + (f" / {count} for {customer}" if needs == "write" else ""),
                   running=True, code=None, started=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ended="", out="", stopped="")
    threading.Thread(target=work, args=(commands,), daemon=True).start()
    return dict(JOB)


def work(commands):
    global PROC
    code = 0

    def say(text):
        JOB["out"] = (JOB["out"] + text)[-60000:]

    def at_quiet():
        try:
            stop("stopped at 4:45 PM: no heavy work in the trading bot's window")
        except Refused:
            pass                                            # the run ended as the timer fired

    secs = until_quiet()
    curfew = threading.Timer(secs, at_quiet) if secs is not None else None
    if curfew:
        curfew.daemon = True
        curfew.start()
    try:
        for cmd in commands:
            with LOCK:                                      # stop() takes the same lock, so a stop never lands between this check and the next start
                if JOB["stopped"]:
                    break
                say(f"$ python -m {' '.join(cmd)}\n")
                PROC = subprocess.Popen([sys.executable, "-m", *cmd], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
                fence(PROC)
            for line in PROC.stdout:
                say(line)
            rc = PROC.wait()
            if rc and not JOB["stopped"]:
                code = rc
                say(f"[failed: exit code {rc}]\n")
    except OSError as err:
        code = 1
        say(f"[could not start: {err}]\n")
    if curfew:
        curfew.cancel()
    if JOB["stopped"]:
        code = code or 1
        say(f"[{JOB['stopped']}]\n")
    PROC = None
    JOB.update(running=False, code=code, ended=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def stop(why="stopped from the dashboard"):
    """Stop the run this dashboard started, with everything that run started (node, ffmpeg), and nothing else."""
    with LOCK:
        proc = PROC
        if not JOB["running"] or proc is None:
            raise Refused("nothing is running")
        JOB["stopped"] = why
        if os.name == "nt":
            K32.TerminateJobObject(FENCE, 1)                # under the lock: no new step can join the job while it is being ended
        else:
            proc.kill()                                     # ponytail: the step itself only; use a process group if this ever runs off Windows


class Handler(BaseHTTPRequestHandler):
    server_version = "ContentFactory"

    def log_message(self, *args):
        pass

    def reply(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text/", "application/json")) else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        why = refuse(self.headers, self.server.server_port, self.server.allow)
        if why:
            return self.reply(403, {"error": why})
        if path == "/":
            return self.reply(200, PAGE.read_bytes(), "text/html")
        if path == "/api/state":
            return self.reply(200, state())
        if path == "/api/job":
            return self.reply(200, JOB)
        found = resolve(path)
        if not found:
            return self.reply(404, {"error": "no such file here"})
        self.send_file(found)

    def send_file(self, path):
        size = path.stat().st_size
        first, last, part = 0, size - 1, False
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")     # phones ask for videos in ranges
        if m and (m[1] or m[2]):
            part = True
            if m[1]:
                first, last = int(m[1]), min(int(m[2]), last) if m[2] else last
            else:
                first = max(0, size - int(m[2]))
            if first > last:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                return self.end_headers()
        ext = path.suffix.lower()
        ctype = TEXT.get(ext) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(206 if part else 200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ext in TEXT else ""))
        self.send_header("Content-Length", str(last - first + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        if part:
            self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
        self.end_headers()
        left = last - first + 1
        try:
            with open(path, "rb") as fh:
                fh.seek(first)
                while left > 0:
                    chunk = fh.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (ConnectionError, OSError):
            pass                                                                    # the browser stopped loading a video

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            size = 0
        # read a small body even when refusing: on Windows, closing with unread bytes resets the connection before the answer arrives
        data = self.rfile.read(size) if 0 < size <= 20000 else b""
        self.close_connection = not data
        why = refuse(self.headers, self.server.server_port, self.server.allow)
        if not why and (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            why = "a POST needs Content-Type application/json"
        if why:
            return self.reply(403, {"error": why})
        try:
            if not data:
                raise Refused("the request is empty or too large")
            body = json.loads(data)
            if not isinstance(body, dict) or not all(isinstance(body.get(k, ""), str) for k in ("action", "brand", "batch", "clip", "piece", "customer", "count")):
                raise Refused("the request needs a JSON object with text values")
            path = urlsplit(self.path).path
            if path == "/api/decision":
                return self.reply(200, save_decision(body.get("brand", ""), body.get("batch", ""), body.get("piece", ""),
                                                     body.get("decision"), body.get("comment")))
            if path == "/api/run":
                return self.reply(200, start(body.get("action", ""), body.get("brand", ""), body.get("batch", ""), body.get("clip", ""),
                                             body.get("customer", ""), body.get("count", "")))
            if path == "/api/stop":
                stop()
                return self.reply(200, {"ok": True})
            self.reply(404, {"error": "no such action"})
        except (Refused, ValueError) as err:
            self.reply(400, {"error": str(err)})
        except OSError as err:                              # a full disk, a folder that went away: say so instead of dropping the line
            self.reply(500, {"error": f"{type(err).__name__}: {err}"})


class Server(ThreadingHTTPServer):
    allow_reuse_address = False         # on Windows the default lets a second copy bind the same port and split the traffic
    daemon_threads = True
    allow = None


def selfcheck():
    import tempfile
    import urllib.error
    import urllib.request
    global RUNS

    # who may ask
    ok = lambda h, allow=None: refuse(h, 8790, allow) is None
    ts = ("laptop.tail1.ts.net", "nate@example.com")
    assert ok({"Host": "127.0.0.1:8790"}) and ok({"Host": "localhost:8790", "Origin": "http://localhost:8790"})
    assert not ok({}) and not ok({"Host": "evil.com"}) and not ok({"Host": "127.0.0.1:9999"})
    assert not ok({"Host": "127.0.0.1:8790", "Origin": "http://evil.com"}) and not ok({"Host": "127.0.0.1:8790", "Origin": "null"})
    assert ok({"Host": "laptop.tail1.ts.net", "Tailscale-User-Login": "Nate@example.com"}, ts)
    assert ok({"Host": "laptop.tail1.ts.net:8443", "Tailscale-User-Login": "nate@example.com", "Origin": "https://laptop.tail1.ts.net:8443"}, ts)
    assert not ok({"Host": "laptop.tail1.ts.net"}, ts) and not ok({"Host": "laptop.tail1.ts.net", "Tailscale-User-Login": "other@example.com"}, ts)
    assert not ok({"Host": "laptop.tail1.ts.net", "Tailscale-User-Login": "nate@example.com"})            # no host allowed: local only
    assert not ok({"Host": "other.tail1.ts.net", "Tailscale-User-Login": "nate@example.com"}, ts)
    # which files
    assert resolve("/STATUS.md") and resolve("/knowledge/hooks.md") and resolve("/brands/builtwithbaron/brand.json")
    assert not ok({"Host": "127.0.0.1:8790", "Sec-Fetch-Site": "cross-site"}) and not ok({"Host": "127.0.0.1:8790", "Sec-Fetch-Site": "same-site"})
    assert ok({"Host": "127.0.0.1:8790", "Sec-Fetch-Site": "same-origin"}) and ok({"Host": "127.0.0.1:8790", "Sec-Fetch-Site": "none"})
    assert ok({"Host": "127.0.0.1:8790", "Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "navigate"})    # a link from Jarvis opens the page
    assert not ok({"Host": "127.0.0.1:8790", "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"})  # another site's <img>
    for bad in ("/knowledge%5chooks.md", "/" + (ROOT / "STATUS.md").as_posix(), "/%5c%5clocalhost%5cshare%5cx.md",   # backslash, drive, network share
                "/.env", "/.git/config", "/.gitignore", "/factory/dashboard.py", "/requirements.txt", "/remotion/package.json",
                "/runs/../factory/gate.py", "/runs/..%2F..%2Fnq-prop-bot/CLAUDE.md", "/runs/%2e%2e/CLAUDE.md/x", "/C:/Windows/win.ini",
                "/brands/..\\..\\session-hub\\HUB.md", "/tmp/edit2.py", "/", "/runs"):
        assert resolve(bad) is None, bad
    # the trading bot's window
    assert quiet_time(datetime(2026, 11, 17, 16, 35)) and quiet_time(datetime(2026, 11, 15, 17, 9))        # a Tuesday, a Sunday
    assert not quiet_time(datetime(2026, 11, 17, 16, 34)) and not quiet_time(datetime(2026, 11, 17, 17, 10))
    assert not quiet_time(datetime(2026, 11, 20, 16, 50)) and not quiet_time(datetime(2026, 11, 21, 16, 50))  # Friday, Saturday
    assert until_quiet(datetime(2026, 11, 17, 16, 34)) == 660 and until_quiet(datetime(2026, 11, 17, 9, 45)) == 7 * 3600
    assert until_quiet(datetime(2026, 11, 17, 16, 45)) is None and until_quiet(datetime(2026, 11, 20, 12, 0)) is None   # too late today; a Friday
    # runs: only names on disk, never typed text
    for bad in (("rm -rf",), ("brand", "no-such-brand"), ("brand", "../.."), ("hooks", "builtwithbaron", "nope"),
                ("hooks", "builtwithbaron", "2026-11-16-batch1 & calc"), ("footage", "builtwithbaron", "footage-standin", "..\\..\\x.mp4"),
                ("write", "builtwithbaron"), ("write", "builtwithbaron", "", "", "Dentists", "10"), ("write", "builtwithbaron", "", "", "Plumbers", "7"),
                ("write", "builtwithbaron", "", "", "Plumbers", "10 & calc"), ("write", "no-such-brand", "", "", "all", "10"),
                ("write", "builtwithbaron", "", "", "Plumbers --model fable", "10"), ("write", "fastfixwork", "", "", "Plumbers", "10")):
        try:
            start(*bad)
            raise AssertionError(f"started {bad}")
        except Refused:
            pass
    assert not JOB["running"] and JOB["id"] == 0
    assert sections("# T\nintro\n## A\none\n\n## B (x)\ntwo\nthree\n") == {"A": "one", "B (x)": "two\nthree"}
    # decisions: saved in the Export format, in a folder of its own
    real = RUNS
    with tempfile.TemporaryDirectory() as tmp:
        RUNS = Path(tmp)
        try:
            folder = RUNS / "b" / "one"
            folder.mkdir(parents=True)
            (folder / "gate.json").write_text(json.dumps({"pieces": {"H01-M1-A": {}}}), encoding="utf-8")
            save_decision("b", "one", "H01-M1-A", "approve", None)
            save_decision("b", "one", "H01-M1-A", None, "louder")
            saved = json.loads((folder / "decisions.json").read_text(encoding="utf-8"))
            assert saved["batch"] == "b:one" and saved["decisions"]["H01-M1-A"]["decision"] == "approve"
            assert saved["decisions"]["H01-M1-A"]["comment"] == "louder" and not (folder / "decisions.json.tmp").exists()
            if os.name == "nt":                             # the file held open: the save says so, and the old file and no leftover remain
                with open(folder / "decisions.json", "rb"):
                    try:
                        save_decision("b", "one", "H01-M1-A", "reject", None)
                        raise AssertionError("saved over an open file")
                    except Refused:
                        pass
                assert json.loads((folder / "decisions.json").read_text(encoding="utf-8")) == saved and not (folder / "decisions.json.tmp").exists()
            for bad in (("b", "one", "H99", "approve"), ("b", "two", "H01-M1-A", "approve"), ("b", "one", "H01-M1-A", "maybe"),
                        ("..", "b", "H01-M1-A", "approve"), ("b", "one", "H01-M1-A", None, "x" * 2001)):
                try:
                    save_decision(*bad)
                    raise AssertionError(f"saved {bad}")
                except Refused:
                    pass
        finally:
            RUNS = real
    # over the wire, against the real folder, read only
    srv = Server(("127.0.0.1", 0), Handler)
    port = srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def ask(path, headers=None, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as err:
            return err.code, err.read(), err.headers
    try:
        assert ask("/")[0] == 200 and b"Content factory" in ask("/")[1]
        st = json.loads(ask("/api/state")[1])
        assert st["brands"] and st["batches"] and st["actions"] and "Now" in st["status"], "state is missing a part"
        assert all("error" not in b for b in st["batches"]), [b.get("error") for b in st["batches"]]
        assert ask("/.env")[0] == 404 and ask("/factory/dashboard.py")[0] == 404 and ask("/runs/../CLAUDE.md/../.git/config")[0] == 404
        assert ask("/api/state", {"Host": "evil.com"})[0] == 403
        assert ask("/STATUS.md", {"Sec-Fetch-Site": "cross-site"})[0] == 403 and ask("/api/state", {"Sec-Fetch-Site": "cross-site"})[0] == 403
        assert ask("/", {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"})[0] == 200 and ask("/STATUS.md", {"Sec-Fetch-Site": "same-origin"})[0] == 200
        assert ask("/")[2]["X-Frame-Options"] == "SAMEORIGIN" and ask("/STATUS.md")[2]["X-Frame-Options"] == "SAMEORIGIN"   # no other site may frame it and borrow a tap
        jsonh = {"Content-Type": "application/json"}
        assert ask("/api/run", {**jsonh, "Origin": "http://evil.com"}, b'{"action":"checks"}')[0] == 403
        assert ask("/api/run", {"Content-Type": "text/plain"}, b'{"action":"checks"}')[0] == 403                # a plain form post
        assert ask("/api/run", jsonh, b'{"action":"format c:"}')[0] == 400
        assert ask("/api/run", jsonh, b'{"action":["checks"]}')[0] == 400
        assert ask("/api/run", jsonh, b'{"action":"write","brand":"builtwithbaron","customer":"Dentists","count":"10"}')[0] == 400
        assert ask("/api/run", jsonh, b'{"action":"write","brand":"builtwithbaron","customer":"Plumbers","count":10}')[0] == 400      # a number, not text
        assert st["counts"] == ["5", "10", "20"] and st["actions"][0]["id"] == "write"
        assert ask("/api/decision", jsonh, b'{"brand":"builtwithbaron","batch":"nope","piece":"H01","decision":"approve"}')[0] == 400
        assert ask("/api/stop", jsonh, b'{"x":"y"}')[0] == 400                                                  # nothing is running
        code, body, head = ask("/STATUS.md", {"Range": "bytes=2-11"})
        assert code == 206 and len(body) == 10 and head["Content-Range"].startswith("bytes 2-11/"), (code, len(body))
        assert ask("/STATUS.md", {"Range": "bytes=99999999-"})[0] == 416
        assert not JOB["running"] and JOB["id"] == 0
    finally:
        srv.shutdown()
        srv.server_close()
    # a run and its stop: a made-up step whose own child writes a heartbeat; stop must end the child's child too
    if quiet_time():
        print("  skipped the stop check: runs are off in the trading bot's window")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            beat = Path(tmp) / "beat"
            tick = f"import time\nfor _ in range(300):\n open({str(beat)!r}, 'a').write('x'); time.sleep(0.1)"
            ACTIONS["nap"] = ("Nap", "", "", [["timeit", "-n", "1", "-r", "1", f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {tick!r}]).wait()"],
                                              ["timeit", "-n", "1", "-r", "1", "pass"]])
            real_until = until_quiet
            try:
                for how in ("[stopped from the dashboard]", "[stopped at 4:45 PM"):         # the Stop button, then the 4:45 timer
                    beat.unlink(missing_ok=True)
                    if how.startswith("[stopped at"):
                        globals()["until_quiet"] = lambda: 3.0
                    start("nap")
                    end = time.time() + 20
                    while not beat.exists() and time.time() < end:
                        time.sleep(0.1)
                    assert beat.exists(), "the test step never started"
                    try:
                        start("nap")
                        raise AssertionError("two runs at once")
                    except Refused:
                        pass
                    if how == "[stopped from the dashboard]":
                        stop()
                    while JOB["running"] and time.time() < end:
                        time.sleep(0.1)
                    time.sleep(0.5)
                    size = beat.stat().st_size
                    time.sleep(0.7)
                    assert not JOB["running"] and JOB["code"] and beat.stat().st_size == size, "stop left the step or its child running"
                    assert JOB["out"].count("$ python -m") == 1 and how in JOB["out"], JOB["out"]   # the second command never started
            finally:
                globals()["until_quiet"] = real_until
                ACTIONS.pop("nap")
    print("dashboard selfcheck passed")


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = lambda name, default=None: args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default
    if args == ["--selfcheck"]:
        selfcheck()
    elif any(a.startswith("-") and a not in ("--port", "--allow-host", "--allow-login") for a in args):
        sys.exit(__doc__)
    else:
        port = int(opt("--port", PORT))
        try:
            server = Server(("127.0.0.1", port), Handler)
        except OSError as err:
            sys.exit(f"Port {port} is taken ({err}). The dashboard may already be running: open http://127.0.0.1:{port}")
        if opt("--allow-host") and opt("--allow-login"):
            server.allow = (opt("--allow-host").lower(), opt("--allow-login").lower())
        print(f"Content factory dashboard on http://127.0.0.1:{port}  (pid {os.getpid()})", flush=True)
        if server.allow:
            print(f"Also allowed through Tailscale: {server.allow[0]}, signed in as {server.allow[1]}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
