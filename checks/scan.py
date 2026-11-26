"""The gate's frame scan (factory.gate.check_frames) over a batch's videos as they are on disk, without re-rendering.
It does not know where a clip or picture fills the frame on purpose, so footage and faceless videos flag those stretches;
the video lane itself skips them. Usage: python -m checks.scan <brand> <batch>"""
import sys

from factory.brand import ROOT, load_brand
from factory.gate import check_frames
from factory.look import videos

slug, batch = sys.argv[1:3]
bg = load_brand(slug)["brand"]["colors"]["bg"]
bad = 0
for pid, files in videos(ROOT / "runs" / slug / batch).items():
    for size, mp4 in files.items():
        found = check_frames(mp4, size, bg)
        bad += bool(found)
        print(pid, size, "; ".join(found) or "all inside the safe zone")
print(f"{slug} {batch}: {bad} videos with a frame outside the safe zone")
