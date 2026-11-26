"""Tests of the real-footage lane beyond the happy path, on the real brand and the stand-in batch.
Files it makes are its own (tmp/, and keeptest-cut.* in the stand-in's clips folder, removed at the end)."""
import copy
import json
import shutil
import subprocess
from factory.brand import ROOT, BrandError, load_brand
from factory.footage import run
from factory.gate import check_video
from factory.video import heard, says, timeline

brand = load_brand("builtwithbaron")
batch = ROOT / "runs" / "builtwithbaron" / "footage-standin"
raw = batch / "media" / "raw" / "standin-phone-clip.mp4"
hooks = json.loads((batch / "hooks.json").read_text(encoding="utf-8"))
spec = json.loads((batch / "videos.json").read_text(encoding="utf-8"))
good = spec["pieces"][0]
hook = next(h for h in hooks["hooks"] if h["id"] == "H29")
tmp = ROOT / "tmp" / "negf"
shutil.rmtree(tmp, ignore_errors=True)
(tmp / "public").mkdir(parents=True)
ff = lambda *a: subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def refused(name, needle, *args, **kw):
    try:
        run(*args, **kw)
    except BrandError as err:
        ok = needle in str(err)
        print(("ok   " if ok else "MISS ") + f"{name}: {err}")
        assert ok, name
        return
    raise AssertionError(f"{name}: was not refused")


# 1. The cutter refuses what it cannot cut.
ff("-f", "lavfi", "-i", "smptehdbars=size=720x1280:rate=30", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "4", "-pix_fmt", "yuv420p", str(tmp / "silent.mp4"))
refused("a clip with no sound in it", "no speech was heard", "builtwithbaron", "footage-standin", str(tmp / "silent.mp4"))
ff("-f", "lavfi", "-i", "smptehdbars=size=720x1280:rate=30", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "4", "-pix_fmt", "yuv420p", str(tmp / "tone.mp4"))
try:
    r = run("builtwithbaron", "footage-standin", str(tmp / "tone.mp4"))
    print(f"NOTE a clip that is only a tone was not refused; the model heard: \"{r['said']}\"")
    for f in (batch / "media" / "clips").glob("tone-cut.*"):
        f.unlink()
except BrandError as err:
    print(f"ok   a clip that is only a tone: {err}")
refused("a clip that is not there", "is not a file", "builtwithbaron", "footage-standin", str(tmp / "nothing.mp4"))
refused("a batch that is not there", "is missing", "builtwithbaron", "no-such-batch", str(raw))
ff("-i", str(raw), "-vn", str(tmp / "soundonly.m4a"))
refused("a sound file with no picture", "has no picture", "builtwithbaron", "footage-standin", str(tmp / "soundonly.m4a"))
for f in (batch / "media" / "clips").glob("soundonly-cut.*"):
    f.unlink()

# 2. --keep puts a dropped take back.
shutil.copyfile(raw, tmp / "keeptest.mp4")
r = run("builtwithbaron", "footage-standin", str(tmp / "keeptest.mp4"), keep=(3,))
base = json.loads((batch / "media" / "clips" / "standin-phone-clip-cut.json").read_text(encoding="utf-8"))
assert [p["n"] for p in r["dropped"]] == [0] and r["said"].lower().count("setting on your phone line") == 2, r["dropped"]
assert r["seconds_after"] > base["seconds_after"] + 3, (r["seconds_after"], base["seconds_after"])
print(f"ok   --keep 3 puts the first take back: {base['seconds_after']} s -> {r['seconds_after']} s, the line is said twice")
for f in (batch / "media" / "clips").glob("keeptest-cut.*"):
    f.unlink()

# 3. What is said on camera goes through the same gate.
def spec_problems(text, ids="F04,F05,F06,F07"):
    piece = copy.deepcopy(good)
    piece["beats"][0]["say"] = [text, ids]
    return piece, check_video(piece, hooks, brand)[1]


def expect(name, problems, needle):
    hit = [p for p in problems if needle in p]
    print(("ok   " if hit else "MISS ") + name + ": " + (hit[0] if hit else f"no problem holds {needle!r}; got {problems}"))
    assert hit, name


line = good["beats"][0]["say"][0]
assert check_video(good, hooks, brand)[1] == []
expect("a never-claim said on camera", spec_problems(line + " You will never miss a call.")[1], "N01")
expect("a number no cited fact holds", spec_problems(line + " It answers in 2 seconds.")[1], "2")
expect("a fact id that is not in facts.md", spec_problems(line, "F04,F99")[1], "F99")
expect("the fact ids left as FILL IN", spec_problems(line, base["beat"]["say"][1])[1], "FILL IN")

# 4. Captions must be what the clip says.
wrong, problems = spec_problems("It's a setting on your phone line. You can turn it off any time.", "F05")
assert len(problems) == 3 and all("cue" in p for p in problems), problems  # three cards cue words this shorter line lacks
del wrong["beats"][0]["rows"]
assert check_video(wrong, hooks, brand)[1] == []
expect("captions that are not what the clip says", timeline(wrong, hook, brand, batch, spec["voice"], tmp / "public")[3], "does not say the line")
missing = copy.deepcopy(good)
missing["beats"][0]["clip"] = "media/clips/nothing.mp4"
expect("a clip that is missing", timeline(missing, hook, brand, batch, spec["voice"], tmp / "public")[3], "is not in the batch folder")

# 4b. Graphics over the footage: each card lands on its cue, and the picture steps closer on the cutter's joins.
tl = timeline(good, hook, brand, batch, spec["voice"], tmp / "public")
assert tl[3] == [] and len(tl[0]["rows"]) == 4 and tl[0]["scenes"][0]["zooms"], tl[3]
for row, cap_text in zip(tl[0]["rows"], ("rings first", "turn it", "virtual assistant", "transfer")):
    near = min(tl[0]["caps"], key=lambda c: abs(c["from"] - row["at"]) if cap_text.split()[0] in c["text"] else 99)
    assert abs(near["from"] - row["at"]) < 1.0, (row, near)
print(f"ok   4 cards land within a second of their words: {[r['at'] for r in tl[0]['rows']]}; steps at {tl[0]['scenes'][0]['zooms']}")
close = copy.deepcopy(good)
close["beats"][0]["rows"][1] = ["ok", "Same as now", "F04", "the way it does"]
assert check_video(close, hooks, brand)[1] == []
expect("two cards too close to read", timeline(close, hook, brand, batch, spec["voice"], tmp / "public")[3], "a card needs")
nocue = copy.deepcopy(good)
nocue["beats"][0]["rows"][0] = ["ring", "Your phone rings first", "F04", "books the job"]
expect("a card whose cue the clip never says", check_video(nocue, hooks, brand)[1], "[kind, text, facts, cue]")
claim = copy.deepcopy(good)
claim["beats"][0]["rows"][0] = ["ok", "Never miss a call again", "F04", "rings first"]
expect("a never-claim on a card", check_video(claim, hooks, brand)[1], "N01")

# 5. The finished video's own sound says the line once, with no long pause left.
for size in ("9x16", "4x5"):
    mp4 = batch / "pieces" / "H29-M3-C-video" / f"{size}.mp4"
    words = heard(mp4)
    text = " ".join(w[0] for w in words)
    assert says(line, words) and text.lower().count("setting on your phone") == 1 and text.lower().count("rings first") == 1, text
    print(f"ok   {size}.mp4 says the line once: \"{text}\"")
print("all footage tests behaved")
