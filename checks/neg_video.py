"""Failure tests for the video lane on the real brand: each bad input must be refused with a problem that names it.
Works on a copy of the batch's voice files in tmp/neg; the batch itself is not touched."""
import copy
import json
import shutil
import subprocess
from factory.brand import ROOT, load_brand
from factory.gate import check_video
from factory.video import timeline, vo_path

brand = load_brand("builtwithbaron")
real = ROOT / "runs" / "builtwithbaron" / "2026-11-16-batch1"
hooks = json.loads((real / "hooks.json").read_text(encoding="utf-8"))
spec = json.loads((real / "videos.json").read_text(encoding="utf-8"))
voice = spec["voice"]
good = next(p for p in spec["pieces"] if p["id"] == "H01-M3-A")
hook = next(h for h in hooks["hooks"] if h["id"] == "H01")
neg = ROOT / "tmp" / "neg"
shutil.rmtree(neg, ignore_errors=True)
shutil.copytree(real / "media", neg / "media")
(neg / "public").mkdir()


def spec_problems(change):
    piece = copy.deepcopy(good)
    change(piece)
    return check_video(piece, hooks, brand)[1]


def sound_problems(change, before=lambda: None):
    piece = copy.deepcopy(good)
    change(piece)
    assert not check_video(piece, hooks, brand)[1], check_video(piece, hooks, brand)[1]   # the words are allowed; only the sound is wrong
    before()
    return timeline(piece, hook, brand, neg, voice, neg / "public")[3]


def expect(name, problems, needle):
    hit = [p for p in problems if needle in p]
    print(("ok   " if hit else "MISS ") + name + ": " + (hit[0] if hit else f"no problem holds {needle!r}; got {problems}"))
    assert hit, name


assert not spec_problems(lambda p: None) and not timeline(good, hook, brand, neg, voice, neg / "public")[3], "the untouched piece must pass"
print("ok   the untouched piece passes")

expect("a fact that is not in facts.md", spec_problems(lambda p: p["beats"][1].__setitem__("say", ["When you don't pick up, the call rolls to the assistant.", "F99"])), "F99")
expect("a never-claim line", spec_problems(lambda p: p["beats"][2].__setitem__("say", ["It answers every call, so you never miss a call.", "F03"])), "N01")
expect("a number no cited fact holds", spec_problems(lambda p: p["beats"][2].__setitem__("say", ["It answers in 2 seconds and books the job.", "F03"])), "2")

new = "When you can't pick up, the call rolls to the assistant."
expect("a voice file that is missing", sound_problems(lambda p: p["beats"][1].__setitem__("say", [new, "F04"])), "voice line missing")

other = vo_path(neg, voice, "Take the free survey. It takes about 60 seconds.")
expect("a voice file that says other words",
       sound_problems(lambda p: p["beats"][1].__setitem__("say", [new, "F04"]), lambda: shutil.copyfile(other, vo_path(neg, voice, new))),
       "does not say the line")

stray = "Your phone rings first, the way it does now."
expect("a voice file with stray sound (the real bad take)",
       sound_problems(lambda p: p["beats"][1].__setitem__("say", [stray, "F04"]), lambda: shutil.copyfile(ROOT / "checks" / "bad-vo-8c6458a55559.mp3", vo_path(neg, voice, stray))),
       "sound that is not the line")

def too_long(p):
    p["beats"].insert(2, {"say": ["It's a setting on your phone line. You can turn it off any time.", "F05"]})
    p["beats"].insert(2, {"say": ["It says it's a virtual assistant, and it can transfer a call to you.", "F06,F07"]})
expect("a video over 20 seconds", sound_problems(too_long), "punch video is 8 to 20 s")

# The presenter path, with a stand-in clip (the still plus the hook's voice line). A test of the code only, not a deliverable.
clip = neg / "media" / "clips" / "standin.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(neg / "media" / "clips" / "h20-presenter.png"), "-i", str(vo_path(neg, voice, hook["spoken"])),
                "-shortest", "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip)], check=True)
pres = copy.deepcopy(good)
pres["lane"] = "presenter"
pres["beats"][0]["clip"] = "media/clips/standin.mp4"
assert not check_video(pres, hooks, brand)[1], check_video(pres, hooks, brand)[1]
tl, total, files, problems = timeline(pres, hook, brand, neg, voice, neg / "public")
assert not problems and tl["scenes"][0]["clip"] == "clip-standin.mp4" and tl["caps"][0]["from"] < 0.5, (problems, tl["scenes"][0])
print(f"ok   presenter path with a stand-in clip: {total} s, clip scene {tl['scenes'][0]['dur']} s, {len(tl['caps'])} captions")
pres["beats"][0]["clip"] = "media/clips/nothing.mp4"
expect("a presenter clip that is missing", timeline(pres, hook, brand, neg, voice, neg / "public")[3], "is not in the batch folder")
print("all video failure tests behaved")
