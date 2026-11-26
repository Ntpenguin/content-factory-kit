"""Station 6, video lane: videos.json -> gate -> a timeline cut to the voice files -> Remotion mp4 in two sizes -> gate -> gate.json.

    python -m factory.video <brand> <batch>            check, render, check again
    python -m factory.video <brand> <batch> --lines    list every voice line with its file, and say which are missing

A beat lasts as long as its sound, so a caption can never run ahead of or behind its own line. Voice
files are named after the voice and the words (media/vo/<hash>.mp3): change a word and the old file no
longer matches, so stale audio cannot slip into a video. This script never calls a paid service; the
voice files and any presenter clip are made beforehand and their cost is logged in spend.md.

Sound, borrowed from Bobble Breakdown: every voice line is brought to one level, a music bed plays far
under the voice and comes up on the end card, a pop lands with each row and a whoosh with each scene
change. The files are in sounds/ (free to use, sources listed there). After the render a speech-to-text
model listens to the finished video and every line must still be heard.

A piece that fails a copy check is not rendered. Any piece that fails stays failed and is listed in
gate.json with its reasons.
"""
import base64
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from factory.brand import ROOT, BrandError, load_brand
from factory.gate import LANES, SIZES, VIDEO_SIZES, check_frames, check_mp4, check_png, check_video, flat, probe, safe, say, tool, write_report
from factory.statics import RENDER, _read

FPS = 30
LEAD, GAP, HOLD, RING = 0.1, 0.25, 0.7, 1.6   # seconds: before a line, after it, extra on the end card, the ring sound
SILENT_END = 1.5                              # seconds an end card with no voice stays up before the hold (filmed footage)
MAX_PACE = 4.2                                # words a second; faster than this and the captions cannot be read
MAX_EXTRA = 1.0                               # seconds of sound in a voice file outside its heard words (a noise, a false start)
SOUNDS = ROOT / "sounds"
VOICE_DB = -20                                # every generated line's mean level; the bed at BED then sits about 17 dB under it
BED, BED_END = 0.12, 0.28                     # the music's volume under the voice, and on the end card once the voice is done
SFX = {"pop": 0.5, "pop-2": 0.5, "whoosh": 0.45}   # volumes: 4 to 8 dB under the voice (Bobble Breakdown's numbers)
SFX_FILE = "fe-{}.wav"                         # the FASTEDITOR pack (Nate, 2026-11-18: "Yes use these sounds"); "{}.wav" puts back the CC0 ones
WHOOSH_LEAD = 0.3                             # a whoosh starts this long before the scene change, so it lands on the cut
LOUD, PEAK = -14.0, -1.5                      # the finished mix: integrated loudness in LUFS (about what feeds play at), and the limiter's ceiling in dB
PUNCH_IN, ZOOM_GAP = 1.1, 1.0                 # filmed footage: the picture steps this much closer (and back) on a cut, at most once in this many seconds.
                                              # Filmed tight? Lower PUNCH_IN, or the closer step crops the top of the head
CARD_GAP = 1.2                                # seconds a pop-up card over footage needs before the next one lands
CUT_AFTER = 3.2                               # a still picture on screen longer than this gets one cut to a closer crop (a cut every 1 to 3 s)


def vo_path(folder, voice, text):
    return folder / "media" / "vo" / (hashlib.sha1(f"{voice['voice_id']}|{text}".encode()).hexdigest()[:12] + ".mp3")


def seconds(path):
    return float(probe(path).get("format", {}).get("duration", 0))


def level(path):
    """(mean, peak) of a sound file in dB."""
    out = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return tuple(float(re.search(rf"{k}_volume: (-?[\d.]+) dB", out)[1]) for k in ("mean", "max"))


def tighten(src, out):
    """A generated voice line with its pauses cut to 0.3 s, at VOICE_DB mean level, or less if its peak would pass -3 dB:
    a pop or a whoosh lands on top of the voice, and the sum must not clip."""
    raw = out.with_name("raw-" + out.name)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-af", TIGHT, "-ar", "44100", str(raw)], check=True)
    mean, peak = level(raw)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(raw), "-af", f"volume={min(VOICE_DB - mean, -3 - peak):.1f}dB", str(out)], check=True)
    raw.unlink()


def loudness(path):
    """Integrated loudness of a file's sound in LUFS (EBU R 128)."""
    out = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])


def master(mp4):
    """Brings the finished video's sound to LOUD; a limiter holds the peaks under PEAK. The picture is copied untouched.
    The limiter takes a little loudness back, so a second pass adds what the first one lost."""
    mp4, src = Path(mp4), Path(mp4).with_name("premaster-" + Path(mp4).name)
    mp4.replace(src)
    gain = LOUD - loudness(src)
    for _ in range(2):
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-c:v", "copy", "-af",
                        f"volume={gain:.1f}dB,alimiter=limit={10 ** (PEAK / 20):.3f}:level=false", "-c:a", "aac", "-b:a", "192k", str(mp4)], check=True)
        short = LOUD - loudness(mp4)
        if abs(short) < 0.4:
            break
        gain += short
    src.unlink()
    return loudness(mp4)


def envelope(path, start, dur):
    """How loud a cut of a sound file is in each video frame, 0 to 1: it drives the call screen's sound bars."""
    rate = FPS * 100
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", str(start), "-t", str(dur), "-i", str(path), "-ac", "1", "-ar", str(rate), "-f", "u8", "-"],
                         capture_output=True, check=True).stdout
    rms = [(sum((b - 128) ** 2 for b in raw[i:i + 100]) / 100) ** 0.5 for i in range(0, len(raw) - 99, 100)]
    top = max(rms, default=0) or 1
    return [round(v / top, 2) for v in rms]


def clip_cuts(clip):
    """Where factory.footage joined two phrases, in seconds of the cut clip, read from the report it wrote beside the clip.
    No report (a clip that did not come from the cutter): no cuts are known, so the picture is left alone."""
    report = Path(clip).with_suffix(".json")
    if not report.is_file():
        return []
    out, at = [], 0.0
    for p in json.loads(report.read_text(encoding="utf-8")).get("kept", [])[:-1]:
        at += p["to"] - p["from"]
        if not out or at - out[-1] >= ZOOM_GAP:
            out.append(round(at, 3))
    return out


def cue_at(text, cue, words):
    """The second a cue is said: its place in the written line by letters, carried over to the heard words.
    ponytail: not a word-for-word match, since the heard words may differ a little from the line; off by a word at most."""
    share = max(0, flat(text).find(flat(cue))) / max(1, len(flat(text)))
    target, seen = share * sum(len(flat(w[0])) for w in words), 0
    for w in words:
        seen += len(flat(w[0]))
        if seen > target:
            return w[1]
    return words[-1][1] if words else 0.0


def holds(total, scenes, rows, head, turns=()):
    """The longest stretch in seconds with no change on screen but the captions: between scene starts, picture cuts,
    rows landing, sentences of the hook appearing and (on a call screen) the speaker changing
    (knowledge/editing-rules.md: a cut every 1 to 3 seconds). Most of these are smaller than a cut; it is a floor, not a pass."""
    marks = sorted({0.0, total} | {s["from"] for s in scenes} | {s["cut"] for s in scenes if s.get("cut")} | {z for s in scenes for z in s.get("zooms", []) + s.get("reveals", [])} | {r["at"] for r in rows} | {h["at"] for h in head} | set(turns))
    return round(max(b - a for a, b in zip(marks, marks[1:])), 1)


def effects(scenes, rows, length=seconds):
    """The sounds the picture earns: a whoosh that lands on each scene change, a pop as each row lands.
    A sound never plays over itself: one that would start before its last play ends is left out."""
    want = [(s["from"] - WHOOSH_LEAD, "whoosh") for s in scenes[1:]] + [(r["at"] + 0.03, ("pop", "pop-2")[i % 2]) for i, r in enumerate(rows)]
    out, busy = [], {}
    for at, name in sorted(want):
        d = length(SOUNDS / SFX_FILE.format(name))
        if at >= busy.get(name, 0):
            busy[name] = at + d
            out.append({"from": round(at, 3), "src": f"sfx-{name}.wav", "start": 0, "dur": round(d, 3), "vol": SFX[name]})
    return out


TIGHT = "silenceremove=start_periods=1:start_threshold=-40dB:stop_periods=-1:stop_duration=0.3:stop_threshold=-40dB"
_model = None


def heard(path, start=0.0, end=None):
    """What a speech-to-text model hears in the file, or in one cut of it: [(word, from, to)], seconds counted from `start`.
    ponytail: nothing is cached, about a second a line; keep results in a file if a batch grows past a few dozen lines."""
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise BrandError("the video lane listens to every voice file and needs the faster-whisper package (model base.en) for the Python that runs it")
        _model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segments, _ = _model.transcribe(str(path), word_timestamps=True, clip_timestamps=[start, end] if end else "0")
    return [(w.word.strip(), round(float(w.start) - start, 3), round(float(w.end) - start, 3)) for s in segments for w in s.words]


def says(text, words):
    """True when the heard words are the line. Letters and digits only, so "10 a.m." equals "10am"."""
    return difflib.SequenceMatcher(None, flat(text), flat("".join(w[0] for w in words))).ratio() >= 0.8


def captions(text, start, dur, who="", words=None):
    """The line in pieces of 2 to 5 words. With heard words, each piece comes up when its first word is spoken;
    without them (or when they don't line up) each piece gets its share of the line's time by letter count."""
    chunks, cur, line = [], [], text.split()
    for i, word in enumerate(line):
        cur.append(word)
        ends = lambda w: w[-1:] in ".,?!:"
        # Close a piece at a pause, or at 4 words, unless one more word reaches the pause (a piece never straddles a full stop).
        if (len(cur) >= 2 and ends(word)) or (len(cur) == 4 and not ends("".join(line[i + 1:i + 2]))) or len(cur) == 5:
            chunks.append(cur)
            cur = []
    if cur:
        if len(cur) == 1 and chunks:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    total, n = sum(len(" ".join(c)) for c in chunks), len(text.split())
    at = [dur * sum(len(" ".join(c)) for c in chunks[:i]) / total for i in range(len(chunks))]
    if words:
        first = [sum(len(c) for c in chunks[:i]) for i in range(len(chunks))]       # index of each piece's first word in the line
        spoken = [0.0] + [min(dur, words[min(len(words) - 1, round(k * len(words) / n))][1]) for k in first[1:]]
        if all(b - a >= 0.2 for a, b in zip(spoken, spoken[1:] + [dur])):
            heard_at = [min(dur, words[min(len(words) - 1, round(k * len(words) / n))][1]) for k in range(n)]
            return [{"from": round(start + a, 3), "dur": round(b - a, 3), "text": " ".join(c), "who": who,
                     # when each word lights, from the caption's start: its heard start, 2 frames early (house setting)
                     "ats": [round(max(0.0, heard_at[k0 + j] - 2 / 30 - a), 3) for j in range(len(c))]}
                    for c, k0, a, b in zip(chunks, first, spoken, spoken[1:] + [dur])]
    return [{"from": round(start + a, 3), "dur": round(b - a, 3), "text": " ".join(c), "who": who}
            for c, a, b in zip(chunks, at, at[1:] + [dur])]


def timeline(piece, hook, brand, folder, voice, pub):
    """Returns (props for the composition, total seconds, {public name: source file}, problems).
    Generated voice lines are written into `pub` with their pauses cut to 0.3 s and leveled; every line is listened to.
    "said" lists each line with its time, for the listen to the finished video."""
    problems, files = [], {}
    scenes, rows, caps, audio, said, wave = [], [], [], [], [], {}
    head = [{"text": hook["onscreen"], "at": 0.0}]
    beats, t = piece["beats"], 0.0
    for i, beat in enumerate(beats):
        kind = "hook" if i == 0 else "end" if i == len(beats) - 1 else "body"
        pair = say(beat, hook)
        text = pair[0] if pair else ""
        at = t + LEAD
        if beat.get("sfx"):
            files["ring.wav"] = None
            audio.append({"from": round(at, 3), "src": "ring.wav", "start": 0, "dur": RING, "vol": 0.5})
            at += RING + (GAP if text else 0)
        d, clip, image, zooms = 0.0, "", "", []
        if beat.get("image"):                       # a faceless beat: a still picture fills the frame while its line plays
            isrc = folder / beat["image"]
            if not isrc.is_file():
                problems.append(f"beat {i + 1}: picture {beat['image']} is not in the batch folder")
                continue
            image = "img-" + isrc.name
            files[image] = isrc
        if text:
            src = brand["dir"] / beat["audio"] if beat.get("audio") else vo_path(folder, voice, text)
            if not beat.get("clip") and not src.is_file():
                problems.append(f"beat {i + 1}: " + (f"audio file {beat['audio']} is not in the brand folder" if beat.get("audio")
                                                    else f"voice line missing: {src.relative_to(folder).as_posix()} for \"{text}\""))
                continue
            start = 0
            if beat.get("clip"):                    # the clip carries this line in its own sound track; no voice file is made for it
                csrc = folder / beat["clip"]
                if not csrc.is_file():
                    problems.append(f"beat {i + 1}: clip {beat['clip']} is not in the batch folder")
                    continue
                clip = name = "clip-" + csrc.name
                files[clip] = csrc
                words = heard(csrc)
                d = min(seconds(csrc), words[-1][2] + 0.3) if words else seconds(csrc)
                if piece["lane"] == "footage":      # the picture steps closer, then back, where the cutter joined two phrases: the jump reads as a cut
                    zooms = [round(t + c, 3) for c in clip_cuts(csrc) if c < d - 0.5]
            elif beat.get("audio"):
                start, d = beat["start"], beat["end"] - beat["start"]
                if start + d > seconds(src) + 0.05:
                    problems.append(f"beat {i + 1}: {beat['audio']} is {seconds(src):.1f} s long; the cut ends at {start + d:.1f} s")
                    continue
                name = "asset-" + src.name
                files[name] = src
                words = heard(src, start, beat["end"])
                wave[round(at * FPS)] = envelope(src, start, d)   # a recorded call: its real sound moves the bars on the call screen
            else:
                name = f"vo-{src.stem}.wav"
                tighten(src, pub / name)
                d = seconds(pub / name)
                words = heard(pub / name)
            if not says(text, words):
                problems.append(f"beat {i + 1}: the sound does not say the line \"{text}\"; heard \"{' '.join(w[0] for w in words)}\"")
                continue
            if not beat.get("audio") and not clip and d - (words[-1][2] - words[0][1]) > MAX_EXTRA:
                problems.append(f"beat {i + 1}: the voice file for \"{text}\" has {d - (words[-1][2] - words[0][1]):.1f} s of sound that is not the line; make it again")
                continue
            if len(text.split()) / d > MAX_PACE:
                problems.append(f"beat {i + 1}: {len(text.split())} words in {d:.1f} s is too fast to read as captions")
            if not clip:
                audio.append({"from": round(at, 3), "src": name, "start": start, "dur": round(d, 3), "vol": 1})
            caps += captions(text, at, d, str(beat.get("who", "")), words)
            said.append((text, round(at, 3), round(d, 3)))
        elif kind == "end" and not beat.get("sfx"):
            d = SILENT_END
        if kind == "hook" and (d or beat.get("sfx")):
            # A headline of two sentences comes up a sentence at a time: the first is there on frame 0, the next when the voice
            # starts its own next sentence, or (a ring, or a voice line cut differently) at its share of the sound by letters.
            parts = re.split(r"(?<=[.?!])\s+", hook["onscreen"])
            mine = [c for c in caps if c["from"] >= at - 0.01] if text else []
            starts = [c["from"] for k, c in enumerate(mine) if k == 0 or mine[k - 1]["text"][-1] in ".?!"]
            if len(starts) != len(parts):
                first, letters = t + LEAD if beat.get("sfx") else at, sum(map(len, parts))
                starts = [first + (at + d - first) * sum(map(len, parts[:k])) / letters for k in range(len(parts))]
            spoken = {c["text"]: c["from"] for c in reversed(mine)}       # a sentence the voice says word for word lands as it is said
            head = [{"text": part, "at": round(spoken.get(part, starts[k]), 3) if k else 0.0} for k, part in enumerate(parts)]
            for a, b in zip(head, head[1:]):
                b["at"] = max(a["at"], b["at"])
        length = (at - t) + d + GAP + (HOLD if kind == "end" else 0)
        if scenes and scenes[-1]["kind"] == kind and not image and piece["lane"] != "board":   # a beat with its own picture, or its own board card, is its own scene
            scenes[-1]["dur"] = round(t + length - scenes[-1]["from"], 3)
        else:
            scenes.append({"from": round(t, 3), "dur": round(length, 3), "kind": kind, "clip": clip, "image": image,
                           **({"part": beat["part"], "widget": beat["widget"]} if beat.get("part") else {}),
                           **({"zooms": zooms, "punch": PUNCH_IN} if zooms else {})})
        for j, row in enumerate(beat.get("rows", [])):
            # Rows land spread over the beat's line, so the second one is not on screen before the voice gets to it.
            # A card over filmed footage lands when the clip says its cue.
            when = at + cue_at(text, row[3], words) if clip and len(row) > 3 else t + LEAD + j * (length - GAP) / len(beat["rows"])
            if clip and rows and rows[-1]["scene"] == len(scenes) - 1 and when - rows[-1]["at"] < CARD_GAP:
                problems.append(f"beat {i + 1} row {j + 1}: \"{row[1]}\" lands {when - rows[-1]['at']:.1f} s after the card before it; "
                                f"a card needs {CARD_GAP} s to be read, and cards go in the order their cues are said")
            rows.append({"scene": len(scenes) - 1, "at": round(when, 3), "kind": row[0], "text": row[1]})
        t += length
    for s in scenes:                                # an opening clip shorter than its scene plays slower rather than run out
        if s["image"].endswith(".mp4"):
            s["rate"] = round(min(1.0, seconds(files[s["image"]]) / s["dur"]), 3)
    for s in scenes:                                # a picture held long gets one cut to a closer crop, on the caption change nearest its middle (or the middle itself)
        if s["image"] and s["dur"] > CUT_AFTER:
            mid = s["from"] + s["dur"] / 2
            on = [c["from"] for c in caps if s["from"] + 1.2 <= c["from"] <= s["from"] + s["dur"] - 1.2]
            best = min(on, key=lambda x: abs(x - mid)) if on else mid
            s["cut"] = round(best if max(best - s["from"], s["from"] + s["dur"] - best) <= 3 else mid, 3)   # off the caption change when that would hold a side past 3 s
    if piece["lane"] == "board" and scenes:         # the list of cards under the hook builds in while the hook is said, a card at a time
        n = sum(1 for s in scenes if s.get("part"))
        scenes[0]["reveals"] = [round(scenes[0]["dur"] * (k + 1) / (n + 1), 3) for k in range(n)]
    for s in scenes:                                # the end card: the logo and the button land first, the address halfway through
        if s["kind"] == "end":
            s.setdefault("cut", round(s["from"] + s["dur"] / 2, 3))
    turns = [c["from"] for a, c in zip(caps, caps[1:]) if wave and c.get("who") != a.get("who")]   # the call screen changes with the speaker
    low, high = LANES[piece["lane"]]
    if not problems and not low <= t <= high:
        problems.append(f"runs {t:.1f} s; a {piece['lane']} video is {low} to {high} s")
    long = [c["text"] for c in caps if len(c["text"].split()) > 5]
    if long:
        problems.append(f"caption \"{long[0]}\" is over 5 words")
    if not problems:
        # A whoosh marks a change of part (hook, body, end), not every picture: at most 3 transitions (knowledge/editing-rules.md).
        fx = effects([s for i, s in enumerate(scenes) if i == 0 or scenes[i - 1]["kind"] != s["kind"]], rows)
        files.update({a["src"]: SOUNDS / SFX_FILE.format(a["src"][4:-4]) for a in fx})
        audio += fx
    tl = {"scenes": scenes, "rows": rows, "caps": caps, "audio": audio, "head": head, "said": said, "hold": holds(t, scenes, rows, head, turns) if scenes else 0}
    if wave:                                        # one value a frame for the whole video; silent where no recording plays
        tl["wave"] = [0] * (round(t * FPS) + 1)
        for at, env in wave.items():
            tl["wave"][at:at + len(env)] = env
        del tl["wave"][round(t * FPS) + 1:]
    return tl, round(t, 3), files, problems


def lines_needed(slug, batch):
    """Every generated voice line: (file, exists, text). The session makes the missing ones, priced and logged first."""
    brand = load_brand(slug)
    folder = ROOT / "runs" / slug / batch
    hooks = {h["id"]: h for h in _read(folder / "hooks.json", "the hook file")["hooks"]}
    spec = _read(folder / "videos.json", "the video spec")
    out = {}
    for piece in spec["pieces"]:
        hook = hooks.get(str(piece.get("id", "")).split("-")[0])
        for beat in piece.get("beats", []) if hook else []:
            pair = say(beat, hook)
            if isinstance(pair, list) and pair and not beat.get("audio") and not beat.get("clip"):   # a clip carries its own line
                path = vo_path(folder, spec["voice"], pair[0])
                out[path.relative_to(folder).as_posix()] = (path.is_file(), pair[0])
    return out


def run(slug, batch):
    from factory.hooks import load_evidence, with_stats
    folder = ROOT / "runs" / slug / batch
    brand = load_brand(slug)
    if (folder / "evidence.md").is_file():              # a hook's big figure cites a [stat] line of the batch's evidence
        brand = with_stats(brand, load_evidence(folder / "evidence.md"))
    hooks = _read(folder / "hooks.json", "the hook file (run factory.hooks first)")
    spec = _read(folder / "videos.json", "the video spec")
    if not (RENDER / "node_modules").is_dir():
        raise BrandError(f"the render folder has no packages: run `npm ci` in {RENDER}")
    b = brand["brand"]
    look = {
        "colors": b["colors"], "fonts": b["fonts"], "footer": b["footer"],
        "lockup": "data:image/png;base64," + base64.b64encode((brand["dir"] / b["logos"]["lockup"]).read_bytes()).decode(),
    }
    bed = spec.get("music", "lofi")                     # "" turns the music off for the batch
    if bed and not (SOUNDS / f"{bed}.mp3").is_file():
        raise BrandError(f"videos.json asks for music \"{bed}\"; there is no {bed}.mp3 in {SOUNDS}")
    work = ROOT / "tmp" / f"video-{slug}-{batch}"       # the renderer's public folder and the frames pulled for checking
    shutil.rmtree(work, ignore_errors=True)
    (work / "public").mkdir(parents=True)
    (work / "frames").mkdir()

    pieces, jobs, plans, listen, skips = {}, [], [], [], {}
    for piece in spec["pieces"]:
        pid = str(piece.get("id"))
        key = f"{pid}-video"                            # a static and a video may share one hook x body x CTA
        lines, problems = check_video(piece, hooks, brand)
        if key in pieces:
            problems.append(f"{pid} is in videos.json twice")
        out = folder / "pieces" / key
        if out.is_dir() and out.parent == folder / "pieces":
            shutil.rmtree(out)                          # an old render must never pass for this run's
        entry = pieces[key] = {"kind": "video", "lane": piece.get("lane"), "lines": lines, "problems": problems, "files": {}, "notes": []}
        if problems:
            continue
        hook = next(h for h in hooks["hooks"] if h["id"] == pid.split("-")[0])
        tl, total, files, late = timeline(piece, hook, brand, folder, spec["voice"], work / "public")
        problems += late
        if problems:
            continue
        entry["seconds"] = total
        skips[key] = [(s["from"], s["from"] + s["dur"]) for s in tl["scenes"] if s["clip"] or s["image"]]   # filled on purpose: the frame scan skips them
        said = tl.pop("said")
        entry["hold"] = tl.pop("hold")
        entry["notes"].append(f"Longest stretch with nothing changing on screen but the captions: {entry['hold']} s (the editing rule is a cut every 1 to 3 s).")
        if bed:                                         # under the voice all the way, up once the last line is done
            files[f"music-{bed}.mp3"] = SOUNDS / f"{bed}.mp3"
            tl["music"] = {"src": f"music-{bed}.mp3", "vol": BED, "top": BED_END,
                           "up": max([at + d for _, at, d in said] + [tl["scenes"][-1]["from"]])}
        listen.append((key, out / f"{VIDEO_SIZES[0]}.mp4", said))   # both sizes carry the same sound; one is listened to
        entry["notes"].append("Sound: " + ("a music bed under the voice, " if bed else "") + "a pop as each row lands and a whoosh on each scene change. "
                              "A speech-to-text model heard every line in the finished video; no person has listened to the mix.")
        if piece["lane"] == "presenter":
            entry["notes"].append(f"Shows a realistic AI person. For New York audiences it must carry the line \"{b['labels'].get('ai_person_ny', 'AI-generated performer')}\" "
                                  "or New York is left out of the audience. The video does not show that line.")
        if spec.get("note"):                            # a line about the whole batch, such as "a test, not an ad"
            entry["notes"].append(str(spec["note"]))
        if piece["lane"] != "board" and any(b.get("image") for b in piece["beats"]):
            entry["notes"].append(("Faceless explainer: an AI voice" if piece["lane"] == "faceless" else "The lines play") + " over AI-made still pictures, with no person asked for in any of them "
                                  "(the prompts are in media/img/prompts.json). No rule can tell whether a picture misleads; look at each one.")
        if piece["lane"] == "board" and piece["beats"][0].get("image"):
            entry["notes"].append(f"Opens on an AI-made clip or picture (media/img/prompts.json) with the figure \"{hook.get('stat', '')}\" from {hook.get('source', '')}, "
                                  "then cuts to the board. Look at the opening: no rule can tell whether it misleads. "
                                  "If it shows a realistic person and runs as a paid ad to New York, it needs the AI label.")
        if piece["lane"] == "board":
            entry["notes"].append("Board lesson: a numbered card for each step, drawn from the spec's rows (the look of the reel Nate sent on 2026-11-19).")
        if piece["lane"] == "footage":
            entry["notes"].append("Filmed footage, cut by factory.footage. A speech-to-text model wrote down the words; read the captions against the clip.")
            cards, steps = len(tl["rows"]), sum(len(s.get("zooms", [])) for s in tl["scenes"])
            if cards or steps:
                entry["notes"].append(f"Graphics over the footage: {cards} pop-up card(s), each landing as its words are said, and {steps} step(s) closer or back on the cuts. "
                                      "No rule can tell whether a card covers the face or a step crops the head; look at the frames.")
        if any(a["src"].startswith("asset-") for a in tl["audio"]):
            entry["notes"].append("Uses the brand's own recorded demo audio; a speech-to-text model matched each cut to its caption, but no person has listened to it here.")
        for name, src in files.items():
            if src:
                shutil.copyfile(src, work / "public" / name)
        text = {where: t for where, t, _ in lines}
        for size in VIDEO_SIZES:
            w, h = SIZES[size]
            # Drawn 2 px inside the zone the gate checks: phone video stores colour at half resolution, so a strong
            # colour on the edge (an amber button on cream) smears one pixel outward. Found with the second brand.
            inset = {k: v + 2 for k, v in safe(size).items()}
            props = {"w": w, "h": h, "fps": FPS, "dur": total, "bare": False, "safe": inset, "brand": look, "piece": {
                "chip": "" if hook["customer"] == "all" else hook["customer"], "headline": text["headline"],
                "label": text.get("label", ""), "cta": text["cta"], "url": text["url"],
                "series": piece.get("series", ""), "stat": text.get("stat", ""), "source": text.get("source", ""), "tint": int(pid[1:pid.index("-")]), **tl}}   # tint: which accent colour a board starts on, so two videos do not open alike
            comp = "Board" if piece["lane"] == "board" else "Punch"
            mp4 = out / f"{size}.mp4"
            jobs.append({"id": comp, "out": str(mp4), "props": props})
            # Frames to check: the first one, and each scene just before it ends (when it holds the most).
            filled = lambda s: bool(s["clip"] or s["image"])    # a clip or a picture fills the frame
            times = [(0.0, filled(tl["scenes"][0]))] + [(s["from"] + s["dur"] - 0.15, filled(s)) for s in tl["scenes"]]
            if tl["caps"]:                              # and the widest caption, half-way through it
                wide = max(tl["caps"], key=lambda cap: len(cap["text"]))
                mid = wide["from"] + wide["dur"] / 2
                times.append((mid, any(filled(s) and s["from"] <= mid < s["from"] + s["dur"] for s in tl["scenes"])))
            times += [(r["at"] + 0.6, True) for r in tl["rows"] if tl["scenes"][r["scene"]]["clip"]]   # each card over footage, once it has landed
            for t, footage in times:
                png = work / "frames" / f"{key}-{size}-{t:05.2f}.png"
                if footage:                             # footage fills the frame, so check the same frame rendered without it
                    jobs.append({"id": comp, "out": str(png), "frame": round(t * FPS), "props": {**props, "bare": True}})
                plans.append((key, size, mp4, t, png, footage, total))

    if (work / "public" / "ring.wav").exists() is False and any("ring.wav" in json.dumps(j["props"]["piece"]["audio"]) for j in jobs):
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={RING}",
                        "-f", "lavfi", "-i", f"sine=frequency=480:duration={RING}", "-filter_complex",
                        f"amix=inputs=2,afade=t=in:d=0.03,afade=t=out:st={RING - 0.08}:d=0.08", str(work / "public" / "ring.wav")], check=True)
    if jobs:
        jobfile = work / "jobs.json"
        jobfile.write_text(json.dumps(jobs), encoding="utf-8")
        done = subprocess.run(["node", "render.mjs", str(jobfile), str(work / "public")], cwd=RENDER, capture_output=True, text=True, encoding="utf-8", errors="replace")
        failures = [line for line in done.stderr.splitlines() if line.startswith("FAILED")]
        print("\n".join(failures), end="\n" if failures else "")
        if done.returncode and not failures:
            raise BrandError("the renderer stopped: " + (done.stderr.strip().splitlines() or ["no message"])[-1])
    checked = set()
    for key, size, mp4, t, png, footage, total in plans:
        entry = pieces[key]
        if (key, size) not in checked:
            checked.add((key, size))
            if mp4.is_file():
                loud = master(mp4)
                entry.setdefault("loudness", {})[size] = loud
                if not LOUD - 1.5 <= loud <= LOUD + 1 or level(mp4)[1] > -0.3:
                    entry["problems"].append(f"{size}: the sound is at {loud} LUFS with a {level(mp4)[1]} dB peak; it should be near {LOUD:g} LUFS and under -0.3 dB")
            entry["problems"] += check_mp4(mp4, size, total)
            if mp4.is_file():
                entry["files"][size] = f"pieces/{key}/{mp4.name}"
                entry["problems"] += check_frames(mp4, size, b["colors"]["bg"], skips[key])
        if mp4.is_file() and not footage:
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", str(png)], capture_output=True)
        entry["problems"] += [f"{p} (at {t:.1f} s)" for p in check_png(png, size, b["colors"]["bg"]) if f"{p} (at {t:.1f} s)" not in entry["problems"]]

    for key, mp4, said in listen:                       # the finished mix: music and effects must not cover a word
        for text, at, d in said if mp4.is_file() else []:
            words = heard(mp4, max(0, at - 0.1), at + d + 0.2)
            if not says(text, words):
                pieces[key]["problems"].append(f"in the finished video the line \"{text}\" is not heard clearly; heard \"{' '.join(w[0] for w in words)}\"")

    write_report(folder, slug, batch, "video", pieces)
    failed = {k: p["problems"] for k, p in pieces.items() if p["problems"]}
    print(f"{len(pieces) - len(failed)} of {len(pieces)} videos pass; {sum(len(p['files']) for p in pieces.values())} files in {folder / 'pieces'}")
    for key, problems in failed.items():
        for p in problems:
            print(f"  FAIL {key}: {p}")
    return not failed


def selfcheck():
    caps = captions("Your phone rings first, same as now.", 1.0, 2.0)
    assert [c["text"] for c in caps] == ["Your phone rings first,", "same as now."], caps
    assert caps[0]["from"] == 1.0 and abs(caps[-1]["from"] + caps[-1]["dur"] - 3.0) < 0.01     # the captions fill the line's time exactly
    assert all(2 <= len(c["text"].split()) <= 5 for c in captions("We can. I have Thursday at 10am or Friday at 1pm. Which works better, and what name?", 0, 6))
    assert [c["text"] for c in captions("One two three four five", 0, 1)] == ["One two three four five"]   # no one-word tail
    assert [c["text"] for c in captions("Now what?", 0, 1, "Caller")] == ["Now what?"]
    assert [c["text"] for c in captions("They didn't leave a message. They called the next shop.", 0, 4)] == ["They didn't leave a message.", "They called the next shop."]
    words = [("Your", 0.0, 0.2), ("phone", 0.2, 0.5), ("rings", 0.5, 0.8), ("first,", 0.8, 1.1), ("same", 1.5, 1.7), ("as", 1.7, 1.8), ("now.", 1.8, 2.0)]
    timed = captions("Your phone rings first, same as now.", 1.0, 2.0, "", words)
    assert timed[1]["from"] == 2.5 and timed[0]["dur"] == 1.5, timed                         # the second caption waits for its first word
    assert timed[0]["ats"] == [0, 0.133, 0.433, 0.733] and timed[1]["ats"] == [0, 0.133, 0.233], timed  # each word lights when heard, 2 frames early
    assert "ats" not in caps[0]                                                                # no heard words: the lit word goes by letter share
    assert captions("Your phone rings first, same as now.", 1.0, 2.0, "", [("x", 0.0, 0.0)] * 7) == caps   # word times that don't line up: letter share
    line = "We can. I have Thursday at 10am or Friday at 1pm."
    assert says(line, [(w,) for w in "We can. I have Thursday at 10 a.m. or Friday at 1 p.m.".split()])
    assert not says(line, [(w,) for w in "Call now and save fifty percent on your first month.".split()])
    assert not says(line, [])
    demo = ROOT / "brands" / "builtwithbaron" / "assets" / "demo-call.mp3"                   # one real listen, on a recording in the repo
    got = heard(demo, 10.48, 14.4)
    assert says(line, got) and not says("Thanks for calling Baron Plumbing, this is Ava.", got), got
    assert 0 <= got[0][1] < 1 and got[-1][2] <= 4.2, got                                    # times count from the start of the cut
    # Sounds: a whoosh lands on each scene change, pops take turns, and a sound never plays over itself.
    fx = effects([{"from": 0}, {"from": 4.0}, {"from": 4.5}, {"from": 9.0}], [{"at": 5.0}, {"at": 5.1}, {"at": 5.2}, {"at": 6.0}],
                 length=lambda p: 1.9 if "whoosh" in p.name else 0.3)
    assert [(a["from"], a["src"]) for a in fx] == [(3.7, "sfx-whoosh.wav"), (5.03, "sfx-pop.wav"), (5.13, "sfx-pop-2.wav"), (6.03, "sfx-pop-2.wav"),
                                                   (8.7, "sfx-whoosh.wav")], fx      # the whoosh at 4.2 and the pop at 5.23 would overlap their last play
    assert all((SOUNDS / SFX_FILE.format(n)).is_file() and (SOUNDS / f"{n}.wav").is_file() for n in SFX) and (SOUNDS / "lofi.mp3").is_file()
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        quiet, out = Path(d) / "quiet.wav", Path(d) / "out.wav"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=1", "-af", "volume=-12dB", str(quiet)], check=True)
        tighten(quiet, out)
        assert abs(level(out)[0] - VOICE_DB) < 1 and level(quiet)[0] < VOICE_DB - 5, (level(quiet), level(out))   # a quiet line comes up to the level
        # The listen to the finished mix: the same cut under loud noise must fail it.
        mix = lambda noise: subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", "10.48", "-t", "3.92", "-i", str(demo), "-f", "lavfi", "-i",
                                            f"anoisesrc=d=3.92:c=pink:a={noise}", "-filter_complex", f"amix=inputs=2:normalize=0:weights={'1 1' if noise < 1 else '0.03 1'}", str(out)], check=True)
        mix(0.01)
        assert says(line, heard(out))
        mix(1)
        assert not says(line, heard(out)), heard(out)
        # The loudness step: a quiet video comes out near LOUD with its peaks under the ceiling, and the picture is still there.
        vid = Path(d) / "v.mp4"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4:r=30", "-ss", "2.3", "-t", "4", "-i", str(demo),
                        "-af", "volume=-9dB", "-shortest", "-pix_fmt", "yuv420p", str(vid)], check=True)
        before, after = loudness(vid), master(vid)
        assert before < LOUD - 4 and abs(after - LOUD) < 1 and level(vid)[1] <= -0.3, (before, after, level(vid))
        assert any(x.get("codec_type") == "video" for x in probe(vid)["streams"]) and not vid.with_name("premaster-v.mp4").exists()
        env = envelope(demo, 2.3, 2.0)
        assert len(env) in (59, 60) and max(env) == 1 and min(env) < 0.2, env                 # one value a frame, loud and quiet both seen
    assert holds(10, [{"from": 0}, {"from": 4, "cut": 6.5}], [{"at": 4.5}], [{"at": 0}, {"at": 1.5}]) == 3.5   # 6.5 to 10 is the longest
    assert holds(10, [{"from": 0}, {"from": 4, "cut": 6.5}], [{"at": 4.5}], [{"at": 0}, {"at": 1.5}], [8.5]) == 2.5   # a speaker change counts
    assert holds(10, [{"from": 0, "zooms": [3.0, 7.0]}], [], [{"at": 0}]) == 4.0             # a step closer on a cut counts as a change
    assert holds(9, [{"from": 0, "reveals": [2.0, 4.0]}, {"from": 6}], [], [{"at": 0}]) == 3.0   # so does a card joining the board's list under the hook
    words = [("Your", 0.0, 0.2), ("phone", 0.2, 0.5), ("rings", 0.5, 0.8), ("first,", 0.8, 1.1), ("same", 1.5, 1.7), ("as", 1.7, 1.8), ("now.", 1.8, 2.0)]
    line = "Your phone rings first, same as now."
    assert cue_at(line, "rings first", words) == 0.5 and cue_at(line, "Same as", words) == 1.5 and cue_at(line, "Your", words) == 0.0
    assert cue_at(line, "same as", [("Your", 0.0, 0.2), ("phones", 0.2, 0.5), ("ring", 0.5, 0.8), ("first", 0.8, 1.1), ("same", 1.5, 1.7), ("as", 1.7, 1.8), ("now", 1.8, 2.0)]) == 1.5   # misheard a little
    with tempfile.TemporaryDirectory() as d:
        clip = Path(d) / "a-cut.mp4"
        assert clip_cuts(clip) == []                                                         # no report beside the clip: the picture is left alone
        clip.with_suffix(".json").write_text(json.dumps({"kept": [{"from": 1, "to": 3}, {"from": 5, "to": 5.4}, {"from": 6, "to": 8}, {"from": 9, "to": 10}]}))
        assert clip_cuts(clip) == [2.0, 4.4], clip_cuts(clip)                                # 2.4 is too soon after 2.0; nothing after the last phrase
    v = {"voice_id": "v1"}
    assert vo_path(Path("x"), v, "Free survey.") != vo_path(Path("x"), v, "Free survey")       # a changed word is a new file
    assert vo_path(Path("x"), v, "Free survey.") != vo_path(Path("x"), {"voice_id": "v2"}, "Free survey.")
    print("video selfcheck passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
    elif len(sys.argv) == 4 and sys.argv[3] == "--lines":
        try:
            for path, (there, text) in lines_needed(sys.argv[1], sys.argv[2]).items():
                print(f"{'have   ' if there else 'MISSING'} {path}  {text}")
        except BrandError as e:
            sys.exit(f"error: {e}")
    elif len(sys.argv) == 3:
        try:
            sys.exit(0 if run(sys.argv[1], sys.argv[2]) else 1)
        except BrandError as e:
            sys.exit(f"error: {e}")
    else:
        sys.exit("usage: python -m factory.video <brand> <batch> [--lines]   |   python -m factory.video --selfcheck")
