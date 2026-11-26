"""The look pass (borrowed from Bobble Breakdown's art-director step): someone looks at every finished video.

    python -m factory.look <brand> <batch>                    a contact sheet per video; lists the ones nobody has looked at
    python -m factory.look <brand> <batch> <piece> "<note>"   saves the look note for that piece
    python -m factory.look --selfcheck

A sheet is six frames across the video, one sheet per size, written beside the video (pieces/<piece>/look-<size>.png).
The note goes in look.json with the hash of every file it was written about, so a note never outlives its render:
after a re-render the review page says the video has not been looked at. Whoever writes the note says who they are
in it; a note from a Claude session is a look at still frames, not a person watching.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from factory.brand import ROOT, BrandError
from factory.gate import probe, tool

FRAMES = 6


def sha(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def videos(folder):
    """{piece id: {size: mp4 path}} for the batch's video pieces whose files exist."""
    if not (folder / "gate.json").is_file():
        raise BrandError(f"{folder / 'gate.json'} is missing: run the video lane first")
    gate = json.loads((folder / "gate.json").read_text(encoding="utf-8"))
    out = {}
    for pid, p in gate["pieces"].items():
        files = {size: folder / rel for size, rel in p["files"].items() if rel.endswith(".mp4") and (folder / rel).is_file()}
        if files:
            out[pid] = files
    return out


def note(folder, pid, files):
    """The saved look note for this piece if it was written about exactly these files, else None."""
    path = folder / "look.json"
    saved = json.loads(path.read_text(encoding="utf-8")).get(pid) if path.is_file() else None
    return saved if saved and saved["sha"] == {size: sha(f) for size, f in files.items()} else None


def save(folder, pid, files, text):
    path = folder / "look.json"
    looks = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    looks[pid] = {"note": text, "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "sha": {size: sha(f) for size, f in files.items()}}
    path.write_text(json.dumps(looks, indent=1, ensure_ascii=False), encoding="utf-8")


def sheet(mp4):
    """Six frames, evenly spread, side by side."""
    out = Path(mp4).with_name(f"look-{Path(mp4).stem}.png")
    dur = float(probe(mp4).get("format", {}).get("duration", 0)) or 1
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps={FRAMES}/{dur:.3f},scale=360:-1,tile={FRAMES}x1",
                    "-frames:v", "1", str(out)], check=True)
    return out


def selfcheck():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        folder = Path(d)
        mp4 = folder / "9x16.mp4"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=108x192:rate=30", "-pix_fmt", "yuv420p", str(mp4)], check=True)
        files = {"9x16": mp4}
        assert note(folder, "P1", files) is None                    # nothing saved yet
        save(folder, "P1", files, "looked")
        assert note(folder, "P1", files)["note"] == "looked"
        assert sheet(mp4).stat().st_size > 1000
        mp4.write_bytes(mp4.read_bytes() + b"x")                    # a re-render: the note is about another file now
        assert note(folder, "P1", files) is None
    print("look selfcheck passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
    elif len(sys.argv) in (3, 5):
        try:
            folder = ROOT / "runs" / sys.argv[1] / sys.argv[2]
            found = videos(folder)
            if len(sys.argv) == 5:
                if sys.argv[3] not in found:
                    raise BrandError(f"no video piece \"{sys.argv[3]}\" in {folder}; there are: {', '.join(found) or 'none'}")
                save(folder, sys.argv[3], found[sys.argv[3]], sys.argv[4])
                print(f"saved the look note for {sys.argv[3]}")
            else:
                for pid, files in found.items():
                    print(pid, "looked at" if note(folder, pid, files) else "NOT LOOKED AT", *(sheet(f) for f in files.values()))
        except BrandError as err:
            sys.exit(f"error: {err}")
    else:
        sys.exit(__doc__)
