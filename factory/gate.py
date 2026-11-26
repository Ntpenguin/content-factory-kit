"""Stations 5 and 7: the piece spec and the automatic checks every piece must pass.

A piece is one hook x body x CTA from the batch matrix, named like H15-M1-A. Its spec holds only what
the hook sheet does not: the layout and the extra lines. Every line of copy is a pair
[text, "F04,F05"] (the facts it rests on) or [text, "scene"] (sets the scene, claims nothing).

    check_piece(piece, hooks, brand)  -> (lines, problems)   a static: copy, limits, claims
    check_video(piece, hooks, brand)  -> (lines, problems)   a video: the same, plus its beats
    check_png(path, size, bg)         -> problems            size, not blank, safe zone
    check_mp4(path, size, seconds)    -> problems            size, codec, length, sound, plays through
    check_frames(path, size, bg, skip) -> problems           the safe zone on every 5th frame of a video

A video is a list of beats: one spoken line (or one sound) and what is on screen while it plays. The
first beat shows the hook and the last shows the call to action, so a video has two scene changes.

What no rule here can do: judge whether a line says the same thing as the fact it cites, or spot a
misspelt word. The review page prints each line beside its facts so a person can.
"""
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from factory.claims import check_copy

SIZES = {"9x16": (1080, 1920), "4x5": (1080, 1350), "1x1": (1080, 1080)}
LAYOUTS = {"plain": 0, "phone": 1, "list": 1, "cols": 2}   # layout -> number of cards
KINDS = {"ok", "miss", "ring", "info"}
MAX_WORDS = {"headline": 7, "row": 8, "support": 16, "title": 4, "cta": 12, "say": 24, "spoken": 150, "speaker": 2, "stat": 2, "source": 8}
LANES = {"punch": (8, 20), "presenter": (8, 25), "footage": (5, 60), "faceless": (10, 25), "board": (10, 45)}   # lane -> shortest and longest video in seconds (knowledge/formats.md)
IMAGE_LANE = "faceless"                                    # a narrated explainer: every beat but the end card plays over a still picture that fills the frame
BOARD_LANE = "board"                                       # a lesson on a dark board (Nate's example reel, 2026-11-19): a numbered card for each body beat, no pictures
WIDGETS = {"list", "phone", "steps", "thread", "flow", "check", "site"}   # how a board card draws its rows; no widget adds a word of its own
CLIP_LANES = ("presenter", "footage")                      # the first beat is a clip that carries its own sound: an AI presenter, or a clip the owner filmed
VIDEO_SIZES = ("9x16", "4x5")
SOUNDS = {"ring"}
MAX_ROWS = 4
MAX_CARDS = 8                                              # pop-up cards over a filmed clip; each lands on words the clip says
MAX_CHARS = {"meta primary": 125, "meta headline": 40}     # Meta cuts longer text off (knowledge/platforms.md)
PIECE_ID = re.compile(r"^(H\d+)-(M\d+)-([A-Z])$")
FAR = 48   # a channel this far from the background counts as content, not as the faint glow


def flat(text):
    """Letters and digits only, so "10 a.m." equals "10am"."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def safe(size):
    """Margins text and logos stay out of (knowledge/platforms.md)."""
    w, h = SIZES[size]
    if size == "9x16":
        return {"top": 270, "bottom": 384, "side": 65}
    return {"top": round(h * 0.05), "bottom": round(h * 0.05), "side": round(w * 0.05)}


def _pair(value, where, problems):
    """A [text, facts-or-scene] pair -> (text, [fact ids]). A bad shape is a problem, not a crash."""
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) for v in value) and value[0].strip()):
        problems.append(f"{where}: must be [text, facts] such as [\"Free survey\", \"F10\"] or [text, \"scene\"]")
        return "", []
    text, src = value
    if src.strip() == "scene":
        return text, []
    ids = [s.strip() for s in src.split(",") if s.strip()]
    if not ids:
        problems.append(f"{where}: names no fact; cite one or mark the line \"scene\"")
    return text, ids


def _start(piece, hooks, brand):
    """The id H15-M1-A -> (hook, body, cta, problems). A missing hook or CTA stops the check."""
    m = PIECE_ID.match(str(piece.get("id", "")))
    if not m:
        return None, None, None, [f"id {piece.get('id')!r} is not like H15-M1-A"]
    hid, body, cta_id = m.groups()
    hook = next((h for h in hooks["hooks"] if h["id"] == hid), None)
    cta = next((c for c in brand["brand"]["ctas"] if c["id"] == cta_id), None)
    if not hook:
        return None, body, cta, [f"hook {hid} is not in hooks.json"]
    problems = []
    if body not in hook["bodies"]:
        problems.append(f"body {body} is not one of {hid}'s bodies ({', '.join(hook['bodies'])})")
    if not cta:
        problems.append(f"CTA {cta_id} is not in brand.json")
    return hook, body, cta, problems


def _rows(rows, where, lines, problems):
    for ri, row in enumerate(rows, 1):
        if not (isinstance(row, list) and len(row) == 3 and row[0] in KINDS):
            problems.append(f"{where} row {ri}: must be [kind, text, facts] with kind one of {', '.join(sorted(KINDS))}")
            continue
        text, ids = _pair(row[1:], f"{where} row {ri}", problems)
        lines.append(("row", text, ids))


def _finish(piece, body, cta, brand, lines, problems, hooks):
    """Label, call to action, the Meta text, then the limits and the claims check on every line."""
    label = piece.get("label")
    labels = brand["brand"].get("labels", {})
    if label and label not in labels:
        problems.append(f"label {label!r} is not in brand.json")
    need = (hooks.get("bodies") or {}).get(body, {}).get("label")    # a body may require a label, e.g. the demo call's "demo_call"
    if need and label != need:
        problems.append(f"body {body} must carry the label \"{need}\" (hooks.json)")
    if label in labels:
        lines.append(("label", labels[label], []))
    lines.append(("cta", cta["text"], list(cta["claims"])))
    lines.append(("url", cta["url"], []))
    for key in ("primary", "headline"):
        where = f"meta {key}"
        text, ids = _pair((piece.get("meta") or {}).get(key), where, problems)
        lines.append((where, text, ids))

    for where, text, ids in lines:
        limit = MAX_WORDS.get(where)
        if limit and len(text.split()) > limit:
            problems.append(f"{where} \"{text}\": {len(text.split())} words (at most {limit})")
        if where in MAX_CHARS and len(text) > MAX_CHARS[where]:
            problems.append(f"{where}: {len(text)} characters (at most {MAX_CHARS[where]})")
        if where != "url":
            problems += [f"{where} \"{text}\": {p}" for p in check_copy(text, ids, brand)]
    return lines, problems


def check_piece(piece, hooks, brand):
    """Returns (lines, problems). lines is [(where, text, [fact ids])]: every word that will be printed."""
    lines = []
    hook, body, cta, problems = _start(piece, hooks, brand)
    if not (hook and cta):
        return lines, problems

    lines.append(("headline", hook["onscreen"], list(hook["facts"])))
    layout = piece.get("layout")
    cards = piece.get("cards", [])
    if layout not in LAYOUTS:
        problems.append(f"layout {layout!r} is not one of {', '.join(LAYOUTS)}")
    elif len(cards) != LAYOUTS[layout]:
        problems.append(f"layout {layout} takes {LAYOUTS[layout]} card(s), found {len(cards)}")
    for ci, card in enumerate(cards, 1):
        if card.get("title"):
            lines.append(("title", card["title"], []))
        rows = card.get("rows", [])
        if not 1 <= len(rows) <= MAX_ROWS:
            problems.append(f"card {ci}: {len(rows)} rows (1 to {MAX_ROWS} allowed)")
        _rows(rows, f"card {ci}", lines, problems)
    if piece.get("support"):
        text, ids = _pair(piece["support"], "support", problems)
        lines.append(("support", text, ids))
    return _finish(piece, body, cta, brand, lines, problems, hooks)


def say(beat, hook):
    """A beat's spoken line as a [text, facts] pair; "hook" stands for the hook's own spoken line. None: nothing is said."""
    if beat.get("say") == "hook":
        return [hook["spoken"], ",".join(hook["facts"]) or "scene"]
    return beat.get("say")


def check_video(piece, hooks, brand):
    """Returns (lines, problems): every word that is spoken or shown, and what is wrong with the spec."""
    lines = []
    hook, body, cta, problems = _start(piece, hooks, brand)
    if not (hook and cta):
        return lines, problems
    lane, beats = piece.get("lane"), piece.get("beats")
    if lane not in LANES:
        problems.append(f"lane {lane!r} is not one of {', '.join(LANES)}")
    filmed = lane == "footage"                              # the clip is the hook and the body, so two beats and no rows will do
    if not (isinstance(beats, list) and (2 if filmed else 3) <= len(beats) <= 8 and all(isinstance(b, dict) for b in beats)):
        return lines, problems + ["beats: a video is 3 to 8 beats (the hook, the body, the call to action); filmed footage may be 2 (the clip, the end card)"]

    lines.append(("headline", hook["onscreen"], list(hook["facts"])))    # on screen from the first frame
    rows = 0
    if lane == BOARD_LANE:                                  # the series name sits over the board for the whole video
        if not (isinstance(piece.get("series"), str) and piece["series"].strip()):
            problems.append("a board video needs \"series\": the few words over the board")
        else:
            lines.append(("title", piece["series"], []))
        for part in ("stat", "source"):                     # a big sourced figure over the opening clip; it cites the hook's facts
            if hook.get(part):
                lines.append((part, hook[part], list(hook["facts"])))
    for i, beat in enumerate(beats, 1):
        where = f"beat {i}"
        want = "hook" if i == 1 else "end" if i == len(beats) else None
        if beat.get("show") != want:
            problems.append(f"{where}: " + (f"must have \"show\": \"{want}\"" if want else "only the first beat shows the hook and only the last shows the end"))
        text = ""
        if say(beat, hook) is not None:
            text, ids = _pair(say(beat, hook), f"{where} say", problems)
            lines.append(("spoken" if filmed and beat.get("clip") else "say", text, ids))
        elif filmed and want == "end" and not (beat.get("audio") or beat.get("clip") or beat.get("sfx")):
            pass                                            # a silent end card: no second voice after the owner's own
        elif beat.get("sfx") not in SOUNDS or beat.get("audio") or beat.get("clip"):
            problems.append(f"{where}: no spoken line. Captions carry every spoken line, so a beat with a voice needs \"say\"; a beat with none needs \"sfx\"")
        if beat.get("sfx") and beat["sfx"] not in SOUNDS:
            problems.append(f"{where}: sound {beat['sfx']!r} is not one of {', '.join(SOUNDS)}")
        if beat.get("who"):
            lines.append(("speaker", str(beat["who"]), []))
        if beat.get("audio") and not (isinstance(beat.get("start"), (int, float)) and isinstance(beat.get("end"), (int, float)) and 0 <= beat["start"] < beat["end"]):
            problems.append(f"{where}: a line cut from an audio file needs \"start\" and \"end\" in seconds")
        if beat.get("rows"):
            over = filmed and bool(beat.get("clip"))        # filmed footage: cards pop up over the clip, each [kind, text, facts, cue]
            if want and not over:
                problems.append(f"{where}: rows belong to the body beats, not the hook or the end")
            rows += len(beat["rows"])
            for ri, row in enumerate(beat["rows"] if over else [], 1):
                if not (isinstance(row, list) and len(row) == 4 and isinstance(row[3], str) and flat(row[3]) and flat(row[3]) in flat(text)):
                    problems.append(f"{where} row {ri}: a card over footage is [kind, text, facts, cue]; the cue is words from the clip's line, and the card lands as they are said")
            _rows([r[:3] if over and isinstance(r, list) and len(r) == 4 else r for r in beat["rows"]], where, lines, problems)
        if lane == BOARD_LANE and not want:                 # every body beat is one card: its name, how it is drawn, 1 to 3 rows
            if not (isinstance(beat.get("part"), str) and beat["part"].strip()):
                problems.append(f"{where}: a board card needs \"part\", its name of 1 to 4 words")
            else:
                lines.append(("title", beat["part"], []))
            if beat.get("widget") not in WIDGETS:
                problems.append(f"{where}: \"widget\" must be one of {', '.join(sorted(WIDGETS))}")
            if not 1 <= len(beat.get("rows") or []) <= 3:
                problems.append(f"{where}: a board card shows 1 to 3 rows")
        if beat.get("clip") and (lane not in CLIP_LANES or i != 1):
            problems.append(f"{where}: a clip goes on the first beat of a presenter or footage video only")
        if lane == IMAGE_LANE and bool(beat.get("image")) != (want != "end"):
            problems.append(f"{where}: a faceless video needs \"image\" on every beat but the end card, and none on the end card")
        elif lane != IMAGE_LANE and beat.get("image") and not (lane == BOARD_LANE and want == "hook")                 and (lane != "punch" or want == "end" or beat.get("audio")):
            # a punch beat may play over a picture (Nate, 2026-11-18); a board opens on a realistic clip or still, then cuts
            # to the board (Nate, 2026-11-19); the end card and a recorded call keep their own screen
            problems.append(f"{where}: a picture (\"image\") goes behind a faceless or punch beat only, or a board's opening, never the end card or a recorded call")
    most = MAX_CARDS if filmed or lane == BOARD_LANE else MAX_ROWS      # a board holds up to 3 rows a card, 8 in all
    if not (0 if filmed or lane == IMAGE_LANE else 1) <= rows <= most:   # in a faceless video the pictures carry the body; rows are extra
        problems.append(f"the body shows {rows} rows (1 to {most} allowed)")
    if lane in CLIP_LANES and not beats[0].get("clip"):
        problems.append(f"a {lane} video needs \"clip\" on its first beat")
    # A study's figure is shown only beside its source (Nate, 2026-11-20: "Yes to all 3"). Only a board's opening draws the
    # source, so a [stat] line may be cited only by a board whose hook cites it, sets "source" and has a picture behind it.
    named = set(hook["facts"]) if lane == BOARD_LANE and hook.get("source") and beats[0].get("image") else set()
    loose = sorted({i for _, _, ids in lines for i in ids if brand["facts"].get(i, {}).get("status", "").startswith("stat")} - named)
    if loose:
        problems.append(f"{', '.join(loose)}: a study's figure needs its source on screen, and only a board video's opening shows one "
                        "(the hook cites the figure, sets \"source\" and has a picture behind it)")
    seen = set()
    lines = [x for x in lines if not (x[0] == "speaker" and (x[1] in seen or seen.add(x[1])))]
    return _finish(piece, body, cta, brand, lines, problems, hooks)


def write_report(folder, slug, batch, kind, pieces):
    """gate.json holds every lane's pieces. A lane replaces only the pieces of its own kind."""
    path = Path(folder) / "gate.json"
    old = json.loads(path.read_text(encoding="utf-8"))["pieces"] if path.is_file() else {}
    merged = {k: v for k, v in old.items() if v.get("kind") != kind} | pieces
    report = {"brand": slug, "batch": batch, "checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "pieces": dict(sorted(merged.items(), key=lambda kv: kv[1]["kind"]))}
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")


def check_png(path, size, bg):
    """The rendered file: right size, not blank, and nothing but background outside the safe zone."""
    from PIL import Image, ImageChops   # Pillow is already in C:\Python314; nothing is installed

    path = Path(path)
    if not path.is_file():
        return [f"{size}: {path.name} was not rendered"]
    im = Image.open(path).convert("RGB")
    if im.size != SIZES[size]:
        return [f"{size}: is {im.size[0]}x{im.size[1]}, should be {SIZES[size][0]}x{SIZES[size][1]}"]
    w, h = im.size
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg))
    r, g, b = diff.split()
    far = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > FAR else 0)
    if not far.getbbox():
        return [f"{size}: the image is blank"]
    s = safe(size)
    bands = {
        "top": (0, 0, w, s["top"]), "bottom": (0, h - s["bottom"], w, h),
        "left": (0, 0, s["side"], h), "right": (w - s["side"], 0, w, h),
    }
    return [f"{size}: something is drawn in the {name} margin (outside the safe zone, or text ran over)"
            for name, box in bands.items() if far.crop(box).getbbox()]


def tool(name):
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} is not on PATH (the video lane needs ffmpeg and ffprobe)")
    return path


def probe(path):
    """ffprobe's facts about a media file: {"streams": [...], "format": {...}}. Empty when it cannot be read."""
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(out.stdout or "{}") if out.returncode == 0 else {}


def check_mp4(path, size, seconds):
    """The rendered video: right size, plays on a phone (h264, 4:2:0, 30 fps), right length, has sound, decodes to the end."""
    path = Path(path)
    if not path.is_file():
        return [f"{size}: {path.name} was not rendered"]
    info = probe(path)
    video = next((x for x in info.get("streams", []) if x.get("codec_type") == "video"), None)
    audio = next((x for x in info.get("streams", []) if x.get("codec_type") == "audio"), None)
    if not video:
        return [f"{size}: {path.name} is not a video file"]
    problems = []
    if (video["width"], video["height"]) != SIZES[size]:
        problems.append(f"{size}: is {video['width']}x{video['height']}, should be {SIZES[size][0]}x{SIZES[size][1]}")
    if video.get("codec_name") != "h264" or video.get("pix_fmt") not in ("yuv420p", "yuvj420p"):
        problems.append(f"{size}: is {video.get('codec_name')} {video.get('pix_fmt')}, should be h264 yuv420p")
    if video.get("r_frame_rate") != "30/1":
        problems.append(f"{size}: frame rate is {video.get('r_frame_rate')}, should be 30")
    length = float(info["format"].get("duration", 0))
    if abs(length - seconds) > 0.25:
        problems.append(f"{size}: runs {length:.1f} s, the timeline says {seconds:.1f} s")
    if not audio:
        problems.append(f"{size}: has no sound track")
    else:
        heard = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        m = re.search(r"mean_volume: (-?[\d.]+|-inf) dB", heard)
        if not m or m[1] == "-inf" or float(m[1]) < -50:
            problems.append(f"{size}: the sound track is silent")
    broken = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(path), "-f", "null", "-"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if broken.returncode or broken.stderr.strip():
        problems.append(f"{size}: does not play through cleanly ({(broken.stderr.strip().splitlines() or ['ffmpeg failed'])[0][:120]})")
    return problems


def check_frames(path, size, bg, skip=(), fps=6):
    """check_png's safe-zone check on 6 frames a second (every 5th frame at 30 fps). The gate's own frames (the first, each
    scene's end, the widest caption) missed a card that pulsed past the edge mid-scene; this found it. Frames inside `skip`
    ((start, end) in seconds, where a clip or picture fills the frame on purpose) are not checked; a blank frame is fine here
    (a scene fading in). One problem per margin, at the first time it happens."""
    import tempfile
    out, hit = [], set()
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(path), "-vf", f"fps={fps}", str(Path(d) / "%05d.png")], check=True)
        for png in sorted(Path(d).glob("*.png")):
            t = (int(png.stem) - 1) / fps
            if any(a <= t <= b for a, b in skip):
                continue
            for p in check_png(png, size, bg):
                if "blank" not in p and p not in hit:
                    hit.add(p)
                    out.append(f"{p} (at {t:.1f} s, frame scan)")
    return out


def selfcheck():
    import tempfile
    from PIL import Image, ImageDraw

    cp = lambda s: re.compile(s, re.I)
    brand = {
        "brand": {"ctas": [{"id": "A", "text": "Take the free 60-second survey", "url": "x.com/survey", "claims": ["F10"]}],
                  "labels": {"demo_call": "Demo call · AI voice"}},
        "facts": {"F10": {"text": "The survey is free and takes about 60 seconds: six taps."},
                  "F04": {"text": "Your phone rings first."}},
        "never": {"N02": {"patterns": [cp("guarantee")], "reason": "no guarantee is public"}},
    }
    hooks = {"bodies": {"M1": {"label": "demo_call"}, "M3": {}},
             "hooks": [{"id": "H01", "onscreen": "Your phone still rings first.", "facts": ["F04"], "bodies": ["M3", "M1"]}]}

    def piece(**change):
        p = {"id": "H01-M3-A", "layout": "list",
             "cards": [{"rows": [["ok", "Six taps", "F10"], ["ring", "Incoming call · 2:07 AM", "scene"]]}],
             "support": ["Free. About 60 seconds.", "F10"],
             "meta": {"primary": ["Your phone still rings first.", "F04"], "headline": ["Free survey", "F10"]}}
        p.update(change)
        return p

    bad = lambda **change: " | ".join(check_piece(piece(**change), hooks, brand)[1])
    lines, problems = check_piece(piece(), hooks, brand)
    assert problems == [], problems
    assert [w for w, _, _ in lines] == ["headline", "row", "row", "support", "cta", "url", "meta primary", "meta headline"]
    assert "not in facts.md" in bad(support=["Free survey.", "F99"])                 # a claim not in facts.md fails
    assert "names no fact" in bad(support=["It books the job.", ""])                 # a claim with nothing behind it
    assert "number 90" in bad(support=["Done in 90 seconds.", "F10"])                # a number its fact does not hold
    assert "number 60" in bad(support=["Takes 60 seconds.", "scene"])                # a scene line cannot carry a claim's number
    assert "never-claim N02" in bad(support=["Results guaranteed.", "F10"])
    assert "body M1 must carry the label" in bad(id="H01-M1-A")                      # demo call without its label
    hooks["bodies"]["M1"] = {}
    assert bad(id="H01-M1-A") == ""                                                   # a brand whose M1 is no demo call needs no label
    hooks["bodies"]["M1"] = {"label": "demo_call"}
    assert "not one of H01's bodies" in bad(id="H01-M4-A")
    assert "CTA Z" in bad(id="H01-M3-Z")
    assert "not like H15-M1-A" in bad(id="hook one")
    assert "takes 2 card(s)" in bad(layout="cols")
    assert "9 words" in bad(cards=[{"rows": [["ok", "one two three four five six seven eight nine", "scene"]]}])
    assert "126 characters" in bad(meta={"primary": ["x" * 126, "scene"], "headline": ["Free survey", "F10"]})
    assert "meta headline: must be" in bad(meta={"primary": ["Fine.", "scene"]})     # a missing line is named, not crashed on

    hooks["hooks"][0]["spoken"] = "Your phone still rings first. This only takes the calls you can't."
    def video(**change):
        v = {"id": "H01-M3-A", "lane": "punch", "meta": piece()["meta"], "beats": [
            {"show": "hook", "say": "hook"},
            {"say": ["It rings you first.", "F04"], "rows": [["ring", "Your phone rings first", "F04"]]},
            {"show": "end", "say": ["Take the free survey. About 60 seconds.", "F10"]}]}
        v.update(change)
        return v
    beats = lambda *edit: [dict(b, **e) for b, e in zip(video()["beats"], edit)]
    vbad = lambda **change: " | ".join(check_video(video(**change), hooks, brand)[1])
    lines, problems = check_video(video(), hooks, brand)
    assert problems == [], problems
    assert [w for w, _, _ in lines] == ["headline", "say", "say", "row", "say", "cta", "url", "meta primary", "meta headline"]
    assert lines[1][2] == ["F04"]                                                    # the hook's spoken line keeps the hook's facts
    assert "lane 'film'" in vbad(lane="film")
    assert "3 to 8 beats" in vbad(beats=video()["beats"][:2])
    assert "beat 1: must have \"show\": \"hook\"" in vbad(beats=beats({"show": None}, {}, {}))
    assert "no spoken line" in vbad(beats=beats({"say": None}, {}, {}))              # a silent beat with no sound named
    assert vbad(beats=beats({"say": None, "sfx": "ring"}, {}, {})) == ""             # a ring instead of a voice is allowed
    assert "no spoken line" in vbad(beats=beats({}, {"say": None, "sfx": "ring", "audio": "a.mp3", "start": 0, "end": 1}, {}))  # a voice with no caption
    assert "sound 'boom'" in vbad(beats=beats({}, {"sfx": "boom"}, {}))
    assert "not in facts.md" in vbad(beats=beats({}, {"say": ["It books the job.", "F99"]}, {}))
    assert "never-claim N02" in vbad(beats=beats({}, {"say": ["Results guaranteed.", "F04"]}, {}))
    assert "number 90" in vbad(beats=beats({}, {}, {"say": ["Done in 90 seconds.", "F10"]}))
    assert "25 words" in vbad(beats=beats({}, {"say": [" ".join(["word"] * 25), "scene"]}, {}))
    assert "body shows 0 rows" in vbad(beats=beats({}, {"rows": []}, {}))
    assert "rows belong to the body" in vbad(beats=beats({"rows": [["ok", "Six taps", "F10"]]}, {}, {}))
    assert "needs \"start\" and \"end\"" in vbad(beats=beats({}, {"audio": "a.mp3"}, {}))
    assert "a clip goes on" in vbad(beats=beats({"clip": "a.mp4"}, {}, {}))          # a clip in a punch video
    assert "needs \"clip\"" in vbad(lane="presenter")
    # Filmed footage: the clip and a silent end card are enough, and the clip's line may be long.
    film = lambda *edit, **change: " | ".join(check_video(video(lane="footage", beats=[dict(b, **e) for b, e in zip(
        [{"show": "hook", "clip": "media/clips/a-cut.mp4", "say": [" ".join(["It rings you first."] * 10), "F04"]}, {"show": "end"}], edit or ({}, {}))], **change), hooks, brand)[1])
    assert film() == "", film()
    assert [w for w, _, _ in check_video(video(lane="footage", beats=[{"show": "hook", "clip": "a.mp4", "say": ["It rings you first.", "F04"]}, {"show": "end"}]), hooks, brand)[0]][:2] == ["headline", "spoken"]
    assert "needs \"clip\"" in film({"clip": None}, {})
    card = lambda *row: film({"rows": [list(row)]}, {})                               # cards over the clip: checked like any row, and each needs its cue
    assert card("ok", "Rings you first", "F04", "rings you first") == "", card("ok", "Rings you first", "F04", "rings you first")
    assert "[kind, text, facts, cue]" in card("ok", "Rings you first", "F04")        # no cue
    assert "[kind, text, facts, cue]" in card("ok", "Rings you first", "F04", "books the job")   # a cue the line does not say
    assert "not in facts.md" in card("ok", "Rings you first", "F99", "rings you first")
    assert "never-claim N02" in card("ok", "Results guaranteed", "F04", "rings you first")
    assert "9 rows (1 to 8 allowed)" in film({"rows": [["ok", "Rings you first", "F04", "rings you first"]] * 9}, {})
    assert "no spoken line" in film({"say": None}, {})                               # a clip with no words written down
    assert "never-claim N02" in film({"say": ["Results guaranteed.", "F04"]}, {})     # what is said on camera is checked like any line
    assert "not in facts.md" in film({"say": ["It rings you first.", "F99"]}, {})
    assert "151 words" in film({"say": [" ".join(["word"] * 151), "scene"]}, {})
    assert "no spoken line" in film({}, {"audio": "a.mp3", "start": 0, "end": 1})    # an end card with a voice still needs its caption
    assert "must carry the label" in vbad(id="H01-M1-A")
    # Faceless: a picture on every beat but the end card, rows optional; a picture in no other lane.
    pics = lambda *edit: " | ".join(check_video(video(lane="faceless", beats=[dict(b, **e) for b, e in zip(
        beats({"image": "a.png"}, {"image": "b.png", "rows": []}, {}), edit or ({}, {}, {}))]), hooks, brand)[1])
    assert pics() == "", pics()
    assert "needs \"image\" on every beat but the end card" in pics({}, {"image": None}, {})
    assert "none on the end card" in pics({}, {}, {"image": "c.png"})
    assert vbad(beats=beats({"image": "a.png"}, {"image": "b.png"}, {})) == ""       # a punch beat may play over a picture, or not
    assert "never the end card" in vbad(beats=beats({}, {}, {"image": "c.png"}))
    assert "never the end card or a recorded call" in vbad(beats=beats({}, {"image": "a.png", "audio": "a.mp3", "start": 0, "end": 1}, {}))
    assert "faceless or punch beat only" in film({"image": "a.png"}, {})            # not over filmed footage
    # Board: a series name, and every body beat a named card with a known widget and 1 to 3 rows; never a picture.
    row = ["ok", "Six taps", "F10"]
    board = lambda *edit, **change: " | ".join(check_video(video(**{"lane": "board", "series": "The survey", "beats": [dict(b, **e) for b, e in zip(
        beats({}, {"part": "The taps", "widget": "steps", "rows": [row]}, {}), edit or ({}, {}, {}))], **change}), hooks, brand)[1])
    assert board() == "", board()
    assert "needs \"series\"" in board(series="")
    assert "needs \"part\"" in board({}, {"part": ""}, {})
    assert "\"widget\" must be one of" in board({}, {"widget": "photo"}, {})
    assert "1 to 3 rows" in board({}, {"rows": [row] * 4}, {})
    assert "1 to 3 rows" in board({}, {"rows": []}, {})
    assert "faceless or punch beat only" in board({}, {"image": "a.png"}, {})
    assert board({"image": "media/img/a.mp4"}, {}, {}) == ""                        # the opening may play over a clip
    assert "never the end card" in board({}, {}, {"image": "a.png"})
    hooks["hooks"][0].update(stat="60", source="Our own survey page")
    assert [w for w, _, _ in check_video(video(lane="board", series="The survey", beats=beats({}, {"part": "The taps", "widget": "steps", "rows": [row]}, {})), hooks, brand)[0]][:4] == ["headline", "title", "stat", "source"]
    assert "number 60" in board()                                                    # the figure must be in the hook's facts (F04 has none)
    hooks["hooks"][0].update(stat="Rings", source="one two three four five six seven eight nine")
    assert "9 words (at most 8)" in board()
    del hooks["hooks"][0]["stat"], hooks["hooks"][0]["source"]
    sb = {**brand, "facts": {**brand["facts"], "E02": {"text": "60% of owners miss calls", "status": "stat, source: x"}}}
    told = {**hooks, "hooks": [dict(hooks["hooks"][0], stat="60%", source="A survey", facts=[*hooks["hooks"][0]["facts"], "E02"]), *hooks["hooks"][1:]]}
    sv = lambda h, first: " | ".join(check_video(video(lane="board", series="The survey", beats=beats(
        first, {"part": "The taps", "widget": "steps", "rows": [["info", "60% miss calls", "E02"]]}, {})), h, sb)[1])
    assert sv(told, {"image": "media/img/a.mp4"}) == "", sv(told, {"image": "media/img/a.mp4"})   # the figure beside its named source
    assert "E02: a study's figure" in sv(told, {})                                   # no picture behind the hook: no opening, no source
    assert "E02: a study's figure" in sv(hooks, {"image": "media/img/a.mp4"})        # the hook names no source
    assert "never-claim N02" in board({}, {"part": "Results guaranteed"}, {})       # a card's name is checked like any line
    assert "5 words (at most 4)" in board(series="One two three four five")

    with tempfile.TemporaryDirectory() as d:
        bg = "#08090a"
        def png(name, size=(1080, 1080), box=None):
            im = Image.new("RGB", size, bg)
            if box:
                ImageDraw.Draw(im).rectangle(box, fill="#ffffff")
            im.save(Path(d) / name)
            return Path(d) / name
        assert check_png(png("ok.png", box=(100, 100, 900, 900)), "1x1", bg) == []
        assert "blank" in check_png(png("blank.png"), "1x1", bg)[0]
        assert "should be 1080x1350" in check_png(png("ok.png", box=(100, 100, 900, 900)), "4x5", bg)[0]
        assert "right margin" in check_png(png("over.png", box=(100, 100, 1060, 900)), "1x1", bg)[0]
        assert "top margin" in check_png(png("tall.png", (1080, 1920), (100, 200, 900, 900)), "9x16", bg)[0]
        assert check_png(png("tall-ok.png", (1080, 1920), (65, 270, 1014, 1535)), "9x16", bg) == []
        assert "not rendered" in check_png(Path(d) / "missing.png", "1x1", bg)[0]

        def mp4(name, size="1080x1350", secs=2, sound="sine=frequency=440", extra=()):
            out = Path(d) / name
            cmd = [tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x08090a:s={size}:r=30:d={secs}"]
            cmd += ["-f", "lavfi", "-i", sound, "-shortest", "-c:a", "aac"] if sound else []
            subprocess.run(cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", *extra, str(out)], check=True)
            return out
        assert check_mp4(mp4("ok.mp4"), "4x5", 2) == []
        assert "should be 1080x1920" in check_mp4(mp4("ok.mp4"), "9x16", 2)[0]
        assert "the timeline says 5.0 s" in check_mp4(mp4("ok.mp4"), "4x5", 5)[0]
        assert "no sound track" in check_mp4(mp4("mute.mp4", sound=None), "4x5", 2)[0]
        assert "silent" in check_mp4(mp4("quiet.mp4", sound="anullsrc=r=44100"), "4x5", 2)[0]
        assert "frame rate" in check_mp4(mp4("slow.mp4", extra=("-r", "24")), "4x5", 2)[0]
        cut = Path(d) / "cut.mp4"
        cut.write_bytes(mp4("ok.mp4").read_bytes()[:3000])                           # a file cut off mid-write
        assert check_mp4(cut, "4x5", 2) != []
        assert "not rendered" in check_mp4(Path(d) / "missing.mp4", "4x5", 2)[0]
        # A box that pokes into the right margin from 1.0 to 1.5 s only: the frame scan finds it, unless that stretch is skipped.
        box = mp4("poke.mp4", secs=3, extra=("-vf", "drawbox=x=1050:y=500:w=20:h=200:color=white:t=fill:enable='between(t,1,1.5)'"))
        found = check_frames(box, "4x5", bg)
        assert len(found) == 1 and "right margin" in found[0] and "at 1.0 s" in found[0], found
        assert check_frames(box, "4x5", bg, skip=[(0.9, 1.6)]) == []
        assert check_frames(mp4("ok.mp4"), "4x5", bg) == []
    print("gate selfcheck passed")


if __name__ == "__main__":
    selfcheck()
