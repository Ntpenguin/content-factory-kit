"""The one-line video (knowledge/editing-rules.md, "One-line style" [S17]): line.json -> copy check -> a timeline cut to the
voice files -> one continuous Remotion shot (remotion/src/Line.tsx) -> loudness, file, safe-zone and listen checks -> gate.json.

    python -m factory.line <brand> <run>      reads runs/<brand>/<run>/line.json
    python -m factory.line --selfcheck

A draft lane: one piece a run, built from voice lines an earlier batch already made ("lines_from"), so it calls no paid
service. Every sound and every move hangs on a time read from the voice files: the phone rings when the hook ends, the
line leaves the phone on the word that says so, each card lights on its own word, the logo lands in a breath of silence.
"""
import base64
import json
import shutil
import subprocess
import sys

from factory.brand import ROOT, BrandError, load_brand
from factory.claims import check_copy
from factory.gate import MAX_WORDS, SIZES, check_mp4, check_png, safe, tool, write_report
from factory.statics import RENDER, _read
from factory.video import (BED, BED_END, FPS, GAP, HOLD, LEAD, LOUD, RING, SFX, SFX_FILE, SOUNDS, captions, cue_at, envelope, heard,
                           level, master, says, seconds, tighten, vo_path)

SLAM = 0.17                 # seconds: the line hits the bottom of the hook bar, with a low hit; frame 0 is already moving
REACH = 0.45                # the line sets off this long before a sound it lands on (MOTION.reach in Line.tsx)
CAM_LEAD, CAM_LAND = 1.0, 0.1   # the camera leaves for the phone this long before the ring and lands this long before it
SETTLE = 0.45               # after the recorded call, before the next line: the camera's move to the cards
BREATH, LOGO = 0.55, 1.0    # silence before the logo lands; how long the logo holds before the end card
HIT = 0.8                   # volume of the low hit (the slam and the logo)
KICK = "aevalsrc=0.9*exp(-7*t)*sin(2*PI*(60*t+4.4*(1-exp(-25*t)))):d=0.9:s=44100"   # a low hit made here: 170 Hz falling to 60 Hz


def timeline(spec, brand, lines, pub):
    """Returns (the composition's piece, seconds, {public name: source file or None for a sound made here}, [(line, at, length)], problems)."""
    problems, files, audio, caps, said = [], {}, [], [], []
    voice = spec["voice"]

    def speak(text, at, who=""):
        """Places a generated voice line at `at`; returns (its length, its heard words), or (0, []) with a problem noted."""
        src = vo_path(lines, voice, text)
        if not src.is_file():
            problems.append(f"voice line missing in {lines.name}: \"{text}\"")
            return 0.0, []
        name = f"vo-{src.stem}.wav"
        tighten(src, pub / name)
        d, words = seconds(pub / name), heard(pub / name)
        if not says(text, words):
            problems.append(f"the sound does not say the line \"{text}\"; heard \"{' '.join(w[0] for w in words)}\"")
        audio.append({"from": round(at, 3), "src": name, "start": 0, "dur": round(d, 3), "vol": 1})
        caps.extend(captions(text, at, d, who, words))
        said.append((text, round(at, 3), round(d, 3)))
        return d, words

    def sound(name, at, vol, src=None):
        public = name if src is None else f"sfx-{name}"
        files[public] = src
        audio.append({"from": round(max(0, at), 3), "src": public, "start": 0, "dur": round(seconds(src), 3) if src else {"ring.wav": RING, "hit.wav": 0.9}[name], "vol": vol})

    sound("hit.wav", SLAM - 0.02, HIT)
    at = SLAM + 0.18
    d, words = speak(spec["hook"][0], at)
    accent = at + cue_at(spec["hook"][0], spec["accent"], words)   # the headline's last words turn to the accent colour as they are said
    ring = at + d + 0.15
    sound("ring.wav", ring, 0.5)
    missed = ring + RING
    at = missed + LEAD
    d, words = speak(spec["roll"][0], at)
    leave = at + cue_at(spec["roll"][0], spec["roll_cue"], words)
    sound("whoosh.wav", leave - 0.1, SFX["whoosh"], SOUNDS / SFX_FILE.format("whoosh"))
    wave0 = at + d + GAP

    call = spec["call"]
    src = brand["dir"] / call["audio"]
    length = call["end"] - call["start"]
    if not src.is_file() or call["end"] > seconds(src) + 0.05:
        problems.append(f"the recording {call['audio']} is missing or shorter than the cut")
        return {}, 0, files, said, problems
    words = heard(src, call["start"], call["end"])
    if not says(call["say"][0], words):
        problems.append(f"the recording does not say \"{call['say'][0]}\"; heard \"{' '.join(w[0] for w in words)}\"")
    files["asset-" + src.name] = src
    audio.append({"from": round(wave0, 3), "src": "asset-" + src.name, "start": call["start"], "dur": round(length, 3), "vol": 1})
    caps.extend(captions(call["say"][0], wave0, length, call["who"], words))
    said.append((call["say"][0], round(wave0, 3), round(length, 3)))
    wave1 = wave0 + length

    at = wave1 + SETTLE
    d, words = speak(spec["does"][0], at)
    cards = [{"text": text, "at": round(at + cue_at(spec["does"][0], cue, words), 3)} for text, cue, _ in spec["cards"]]
    for i, card in enumerate(cards):
        name = ("pop", "pop-2")[i % 2]
        sound(f"{name}.wav", card["at"] + 0.03, SFX[name], SOUNDS / SFX_FILE.format(name))
    hero = at + d + BREATH
    sound("hit.wav", hero, HIT)
    end = hero + LOGO
    cta = next(c for c in brand["brand"]["ctas"] if c["id"] == spec["cta"])
    d, _ = speak(cta["text"], end + 0.15)
    up = end + 0.15 + d
    total = up + GAP + HOLD

    marks = {"slam": SLAM, "accent": accent, "ring": ring, "missed": missed, "leave": leave, "wave": [wave0, wave1], "hero": hero, "end": end}
    camera = [[0, 0], [ring - CAM_LEAD, 0], [ring - CAM_LAND, 1], [leave + 0.1, 1], [wave0 + 0.1, 2], [wave1 - 0.1, 2],
              [cards[0]["at"] + 0.2, 3], [hero - REACH - 0.1, 3], [hero - 0.02, 4], [total, 4]]
    order = [SLAM, ring - REACH, ring, missed, leave, wave0, wave1, *(c["at"] for c in cards), hero - REACH - 0.35, hero, end, total]
    if not problems and (order != sorted(set(order)) or [c[0] for c in camera] != sorted({c[0] for c in camera})):
        problems.append(f"the moves do not fit their sounds in order: {[round(x, 2) for x in order]}; a line is too short for the move it carries")
    long = [c["text"] for c in caps if len(c["text"].split()) > 5]
    if long:
        problems.append(f"caption \"{long[0]}\" is over 5 words")
    wave = [0] * (round(total * FPS) + 1)
    env = envelope(src, call["start"], length)
    wave[round(wave0 * FPS):round(wave0 * FPS) + len(env)] = env
    piece = {
        "chip": spec.get("chip", ""), "headline": spec["headline"], "accent": spec["accent"],
        "phone": {k: v[0] for k, v in spec["phone"].items()}, "who": call["who"], "label": brand["brand"]["labels"][call["label"]],
        "cards": cards, "cta": cta["text"], "url": cta["url"],
        "marks": {k: [round(x, 3) for x in v] if isinstance(v, list) else round(v, 3) for k, v in marks.items()},
        "camera": [[round(a, 3), b] for a, b in camera], "wave": wave[:round(total * FPS) + 1], "caps": caps, "audio": audio,
    }
    if spec.get("music"):
        files[f"music-{spec['music']}.mp3"] = SOUNDS / f"{spec['music']}.mp3"
        piece["music"] = {"src": f"music-{spec['music']}.mp3", "vol": BED, "top": BED_END, "up": round(up, 3), "breath": [round(hero - BREATH + 0.05, 3), round(hero, 3)]}
    return piece, round(total, 3), files, said, problems


def copy_lines(spec, brand):
    """Every line the video shows or says, as (where, text, fact ids), with what the copy rules say against it."""
    cta = next((c for c in brand["brand"]["ctas"] if c["id"] == spec["cta"]), None)
    if not cta:
        return [], [f"line.json asks for CTA {spec['cta']}; brand.json has no such CTA"]
    lines = [("headline", spec["headline"], ""), ("hook, spoken", *spec["hook"]), ("line: the call rolls over", *spec["roll"]),
             ("recorded call", *spec["call"]["say"]), ("line: what it does", *spec["does"]), ("cta", cta["text"], ",".join(cta["claims"]))]
    lines += [(f"phone screen: {k}", *v) for k, v in spec["phone"].items()] + [(f"card {i + 1}", text, facts) for i, (text, _, facts) in enumerate(spec["cards"])]
    problems = [f"{where}: {p}" for where, text, facts in lines for p in check_copy(text, [f for f in facts.split(",") if f], brand)]
    if len(spec["headline"].split()) > MAX_WORDS["headline"] or not spec["headline"].endswith(spec["accent"]):
        problems.append(f"headline: over {MAX_WORDS['headline']} words, or it does not end with its accent words \"{spec['accent']}\"")
    problems += [f"card {i + 1}: over {MAX_WORDS['row']} words" for i, (text, _, _) in enumerate(spec["cards"]) if len(text.split()) > MAX_WORDS["row"]]
    if len(spec["cards"]) != 3:
        problems.append("the video has three cards, no more and no fewer")
    return lines, problems


def holds(camera, total):
    """The stretches where the camera rests on a stop, as (start, end) in seconds: only there is the safe zone checked."""
    return [(a[0] + 0.05, min(b[0], total) - 0.05) for a, b in zip(camera, camera[1:]) if a[1] == b[1] and b[0] - a[0] > 0.3]


def run(slug, name):
    brand = load_brand(slug)
    folder = ROOT / "runs" / slug / name
    spec = _read(folder / "line.json", "the one-line video's spec")
    b = brand["brand"]
    lines, problems = copy_lines(spec, brand)
    entry = {"kind": "video", "lane": "line", "lines": lines, "problems": problems, "files": {}, "notes": []}
    out = folder / "pieces" / "line-video"
    work = ROOT / "tmp" / f"line-{slug}-{name}"
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)              # an old render must never pass for this run's
    (work / "public").mkdir(parents=True)
    plans, said = [], []
    if not problems:
        piece, total, files, said, late = timeline(spec, brand, ROOT / "runs" / slug / spec["lines_from"], work / "public")
        problems += late
    if not problems:
        entry["seconds"] = total
        for public, src in files.items():
            if src:
                shutil.copyfile(src, work / "public" / public)
        ff = [tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i"]
        subprocess.run(ff + [KICK, str(work / "public" / "hit.wav")], check=True)
        subprocess.run(ff + [f"sine=frequency=440:duration={RING}", "-f", "lavfi", "-i", f"sine=frequency=480:duration={RING}", "-filter_complex",
                             f"amix=inputs=2,afade=t=in:d=0.03,afade=t=out:st={RING - 0.08}:d=0.08", str(work / "public" / "ring.wav")], check=True)
        look = {"colors": b["colors"], "fonts": b["fonts"], "footer": b["footer"],
                "lockup": "data:image/png;base64," + base64.b64encode((brand["dir"] / b["logos"]["lockup"]).read_bytes()).decode()}
        rest = holds(piece["camera"], total)
        wide = max(piece["caps"], key=lambda c: len(c["text"]))
        times = sorted({round(x, 2) for a, z in rest for x in (a, (a + z) / 2, z)} |
                       {round(wide["from"] + wide["dur"] / 2, 2)} & {round(wide["from"] + wide["dur"] / 2, 2) for a, z in rest if a <= wide["from"] + wide["dur"] / 2 <= z})
        jobs = []
        for size in spec.get("sizes", ["9x16"]):
            w, h = SIZES[size]
            props = {"w": w, "h": h, "fps": FPS, "dur": total, "bare": False, "safe": {k: v + 2 for k, v in safe(size).items()}, "brand": look, "piece": piece}
            mp4 = out / f"{size}.mp4"
            jobs.append({"id": "Line", "out": str(mp4), "props": props})
            for t in times:                             # the same frame without the line, which may cross the margins: text, logo and objects must not
                png = work / "frames" / f"{size}-{t:05.2f}.png"
                jobs.append({"id": "Line", "out": str(png), "frame": round(t * FPS), "props": {**props, "bare": True}})
                plans.append((size, mp4, t, png))
        jobfile = work / "jobs.json"
        jobfile.write_text(json.dumps(jobs), encoding="utf-8")
        done = subprocess.run(["node", "render.mjs", str(jobfile), str(work / "public")], cwd=RENDER, capture_output=True, text=True, encoding="utf-8", errors="replace")
        failures = [line for line in done.stderr.splitlines() if line.startswith("FAILED")]
        if done.returncode and not failures:
            raise BrandError("the renderer stopped: " + (done.stderr.strip().splitlines() or ["no message"])[-1])
        problems += failures
        for size in dict.fromkeys(p[0] for p in plans):
            mp4 = out / f"{size}.mp4"
            if mp4.is_file():
                loud = master(mp4)
                entry.setdefault("loudness", {})[size] = loud
                if not LOUD - 1.5 <= loud <= LOUD + 1 or level(mp4)[1] > -0.3:
                    problems.append(f"{size}: the sound is at {loud} LUFS with a {level(mp4)[1]} dB peak; it should be near {LOUD:g} LUFS and under -0.3 dB")
                entry["files"][size] = f"pieces/line-video/{mp4.name}"
            problems += check_mp4(mp4, size, total)
        for size, mp4, t, png in plans:
            problems += [f"{p} (at {t:.1f} s)" for p in check_png(png, size, b["colors"]["bg"])]
        first = out / f"{plans[0][0]}.mp4"
        for text, at, d in said if first.is_file() else []:   # the finished mix: music and effects must not cover a word
            words = heard(first, max(0, at - 0.1), at + d + 0.2)
            if not says(text, words):
                problems.append(f"in the finished video the line \"{text}\" is not heard clearly; heard \"{' '.join(w[0] for w in words)}\"")
        entry["notes"] += [
            "One continuous shot, no cuts: the camera follows one line of light in the brand's accent colour from the hook to the logo.",
            f"The safe zone was checked on {len(times)} frames where the camera rests, drawn without the line. While the camera moves, "
            "the line and the objects cross the top and bottom margins on purpose; nothing checks those frames.",
            "Sound: a low hit on the slam and on the logo, the ring, one whoosh, a pop on each card, a music bed that stops for a breath before the logo. "
            "A speech-to-text model heard every line in the finished video; no person has listened to the mix.",
            f"Uses the brand's own recorded demo audio and the voice lines in runs/{slug}/{spec['lines_from']} (what they cost is in spend.md).",
        ] + ([str(spec["note"])] if spec.get("note") else [])
    write_report(folder, slug, name, "video", {"line-video": entry})
    print(("PASS" if not problems else "FAIL") + f" line-video: {entry.get('seconds', 0)} s, {entry['files']}")
    for p in problems:
        print(f"  FAIL {p}")
    return not problems


def selfcheck():
    assert holds([[0, 0], [2, 0], [3, 1], [5, 1], [5.2, 2], [5.4, 2], [9, 3]], 8) == [(0.05, 1.95), (3.05, 4.95)]   # a rest under 0.3 s is not one
    brand = load_brand("builtwithbaron")
    spec = {"headline": "Watch a call nobody picks up.", "accent": "nobody picks up.", "hook": ["Watch this.", ""], "roll": ["It rolls to the assistant.", "F04"],
            "call": {"say": ["Hello.", "F25"]}, "does": ["It answers.", "F27"], "phone": {"missed": ["No answer", ""]}, "cta": "C",
            "cards": [["Answers the call", "answers", "F27"], ["Books the job", "books", "F27"], ["Sends you the details", "sends", "F27"]]}
    lines, problems = copy_lines(spec, brand)
    assert not problems and len(lines) == 10, problems
    bad = {**spec, "cards": [["Never miss a call", "answers", "F27"], *spec["cards"][1:]], "accent": "a call."}
    got = copy_lines(bad, brand)[1]
    assert any("never-claim N01" in p for p in got) and any("accent" in p for p in got) and len(got) == 2, got   # a banned promise and a wrong accent are both caught
    assert copy_lines({**spec, "cta": "Z"}, brand)[1]
    print("line selfcheck passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
    elif len(sys.argv) == 3:
        try:
            sys.exit(0 if run(sys.argv[1], sys.argv[2]) else 1)
        except BrandError as e:
            sys.exit(f"error: {e}")
    else:
        sys.exit("usage: python -m factory.line <brand> <run>   |   python -m factory.line --selfcheck")
