"""Station 6, real footage: a filmed clip -> the same clip with the pauses and the repeated takes cut out.

    python -m factory.footage <brand> <batch> <clip> [--keep 2,5]
    python -m factory.footage --selfcheck

Writes media/clips/<name>-cut.mp4 and <name>-cut.json in the batch folder. The json lists what was kept,
what was dropped and why, what the cut clip says, and a first beat to paste into videos.json (lane
"footage"). The video lane then adds the hook on screen, captions timed to the heard words and the end
card, and the gate checks the words like any other piece: python -m factory.video <brand> <batch>.

Pauses are found in the sound itself. A speech-to-text model's word times smear across a pause and it
smooths over a repeated start, so each stretch of speech is listened to on its own.

A filmed line is whatever the person said. The model writes it down, so read the "say" text against the
clip, fix what was misheard and cite its facts before running the video lane.
"""
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

from factory.brand import ROOT, BrandError, load_brand
from factory.gate import tool
from factory.video import heard, says, seconds

QUIET = "-35dB"         # sound below this is a pause. A real room is never silent: raise it (-30dB, -25dB) if a noisy clip comes back uncut
PAUSE = 0.5             # a pause longer than this ends a phrase and is cut out
BEFORE, AFTER = 0.1, 0.15   # seconds of the pause kept around each phrase
LOOK = 3                # a phrase is an earlier take when one of the next 3 phrases starts the same way
SAME = 0.8


def pauses(path, longer=PAUSE):
    """[(from, to)] for every pause in the clip's sound, by ffmpeg's silencedetect."""
    log = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", f"silencedetect=noise={QUIET}:d={longer}", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    starts = [max(0.0, float(x)) for x in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", log)]
    return list(zip(starts, ends + [sound_seconds(path)] * (len(starts) - len(ends))))     # a pause that runs to the end has no end line


def sound_seconds(path):
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if re.fullmatch(r"[\d.]+", out) else seconds(path)


def sounds(quiet, total):
    """The stretches between the pauses. Anything under 0.15 s is a click, not a word."""
    edges = [0.0] + [x for pair in quiet for x in pair] + [total]
    return [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b - a >= 0.15]


def retakes(texts, keep=()):
    """Indexes of phrases to drop: a later phrase starts with the same words, so this one was a false start or an
    earlier take. The last take wins.
    ponytail: a repeat inside one breath (no pause) is not seen, and a repeat meant for effect is dropped; the report
    lists every dropped phrase and --keep puts one back. Compare takes by sound if this misfires on real clips."""
    flat = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in texts]
    drop = set()
    for i, a in enumerate(flat):
        if i in keep or i in drop or len(texts[i].split()) < 2:
            continue
        # The later take may be split by its pauses differently, so compare with the phrases from j on, joined.
        again = [j for j in range(i + 1, min(len(flat), i + 1 + LOOK))
                 if difflib.SequenceMatcher(None, a, "".join(flat[j:j + LOOK])[:len(a)]).ratio() >= SAME]
        if again:
            drop |= set(range(i, again[-1])) - set(keep)     # everything said before the speaker started again
    return drop


def cut(src, keep, dst):
    """One ffmpeg pass: trim each kept piece and join them. Phones film at a changing frame rate, so pieces are cut by time, not by frame count."""
    video = any(s.get("codec_type") == "video" for s in json.loads(subprocess.run(
        [tool("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(src)], capture_output=True, text=True, check=True).stdout)["streams"])
    if not video:
        raise BrandError(f"{src} has no picture; the footage lane needs a filmed clip")
    graph = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}];" for i, (a, b) in enumerate(keep))
    graph += "".join(f"[v{i}][a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][a];[v]scale='min(1080,iw)':-2,fps=30[vo]"
    done = subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-filter_complex", graph, "-map", "[vo]", "-map", "[a]",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "44100", str(dst)], capture_output=True, text=True)
    if done.returncode:
        raise BrandError("ffmpeg could not cut the clip: " + (done.stderr.strip().splitlines() or ["no message"])[-1])


def run(slug, batch, clip, keep=()):
    load_brand(slug)
    folder = ROOT / "runs" / slug / batch
    src = Path(clip)
    if not folder.is_dir():
        raise BrandError(f"{folder} is missing: make the batch first (python -m factory.hooks {slug} {batch})")
    if not src.is_file():
        raise BrandError(f"clip {src} is not a file")
    total = sound_seconds(src)
    parts = []                                          # every stretch of sound, with the words heard in it alone
    for a, b in sounds(pauses(src), total):
        a, b = round(max(0.0, a - BEFORE), 3), round(min(total, b + AFTER), 3)
        text = " ".join(w[0] for w in heard(src, a, b))
        parts.append({"n": len(parts), "from": a, "to": b, "text": text if re.search(r"\w", text) else ""})     # the model writes "." for a noise
    texts = [p["text"] for p in parts]
    if not any(texts):
        raise BrandError(f"no speech was heard in {src.name}; nothing to cut")
    again = retakes(texts, set(keep))
    for p in parts:
        p["why"] = "" if p["n"] in keep else "no words heard (a noise)" if not p["text"] else "a later phrase starts the same way (an earlier take)" if p["n"] in again else ""
    kept = [p for p in parts if not p["why"]]
    dst = folder / "media" / "clips" / f"{src.stem}-cut.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    cut(src, [(p["from"], p["to"]) for p in kept], dst)

    said = " ".join(p["text"] for p in kept)
    whole = heard(dst)
    line = " ".join(w[0] for w in whole) if says(said, whole) else said
    left = [round(b - a, 2) for a, b in pauses(dst, PAUSE + BEFORE + AFTER)]
    report = {
        "source": str(src), "seconds_before": round(total, 2), "seconds_after": round(seconds(dst), 2),
        "kept": kept, "dropped": [p for p in parts if p["why"]], "said": said,
        "heard_in_one_pass": " ".join(w[0] for w in whole), "pauses_left": left,
        "beat": {"show": "hook", "clip": dst.relative_to(folder).as_posix(), "say": [line, "FILL IN: fact ids, after reading this text against the clip"]},
    }
    dst.with_suffix(".json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{dst}: {report['seconds_before']} s -> {report['seconds_after']} s; kept {len(kept)} phrases, dropped {len(report['dropped'])}")
    for p in report["dropped"]:
        print(f"  dropped {p['n']} ({p['from']:.1f}-{p['to']:.1f} s): \"{p['text']}\" ({p['why']})")
    print(f"  the cut says: \"{said}\"")
    if left:
        print(f"  WARNING: {len(left)} pauses longer than {PAUSE + BEFORE + AFTER:.2f} s are still in the cut: {left}")
    return report


def selfcheck():
    assert sounds([(0.0, 1.0), (2.2, 3.7), (9.0, 10.0)], 10.0) == [(1.0, 2.2), (3.7, 9.0)]          # pauses at both ends
    assert sounds([(1.0, 2.0)], 5.0) == [(0.0, 1.0), (2.0, 5.0)]                                    # sound at both ends
    assert sounds([(0.0, 1.0), (1.05, 2.0)], 2.0) == []                                             # a click between two pauses is not speech
    assert sounds([], 3.0) == [(0.0, 3.0)]
    take = ["Your phone still", "Your phone still rings first.", "It's a setting.", "You can turn it off.", "It's a setting.", "You can turn it off.", "Call us today."]
    assert retakes(take) == {0, 2, 3}, retakes(take)            # the false start and the first take of the two-phrase line
    assert retakes(take, keep={3}) == {0, 2}                    # --keep puts a phrase back
    assert retakes(["Yes.", "Yes. We answer."]) == set()        # one word is never called a retake
    assert retakes(["We answer calls.", "We book jobs."]) == set()
    assert retakes(["Your phones still", "", "Your phone still rings."]) == {0, 1}  # misheard a little, with a noise between
    assert retakes(["It's a setting. You can turn it off.", "It's a setting.", "You can turn it off."]) == {0}      # the second take pauses where the first did not
    assert retakes(["It's a setting.", "You can turn it off.", "It's a setting. You can turn it off."]) == {0, 1}   # and the other way round
    print("footage selfcheck passed")


if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        if args == ["--selfcheck"]:
            selfcheck()
        elif len(args) == 3 or (len(args) == 5 and args[3] == "--keep"):
            run(*args[:3], keep=[int(n) for n in args[4].split(",")] if len(args) == 5 else ())
        else:
            sys.exit("usage: python -m factory.footage <brand> <batch> <clip> [--keep 2,5]  |  --selfcheck")
    except BrandError as err:
        sys.exit(f"error: {err}")
