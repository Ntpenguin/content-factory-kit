"""Station 6, statics lane: statics.json -> gate -> Remotion stills in three sizes -> gate -> gate.json.

    python -m factory.statics <brand> <batch>

A piece that fails a copy check is not rendered. Any piece that fails stays failed and is listed in
gate.json with its reasons; the review page shows it that way.
"""
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

from factory.brand import ROOT, BrandError, load_brand
from factory.gate import SIZES, check_piece, check_png, safe, write_report

RENDER = ROOT / "remotion"


def _read(path, what):
    if not path.is_file():
        raise BrandError(f"{what} is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BrandError(f"{path} is not valid JSON: {e}")


def run(slug, batch):
    brand = load_brand(slug)
    folder = ROOT / "runs" / slug / batch
    hooks = _read(folder / "hooks.json", "the hook file (run factory.hooks first)")
    spec = _read(folder / "statics.json", "the statics spec")
    if not (RENDER / "node_modules").is_dir():
        raise BrandError(f"the render folder has no packages: run `npm ci` in {RENDER}")
    b = brand["brand"]
    lockup = brand["dir"] / b["logos"]["lockup"]
    look = {
        "colors": b["colors"], "fonts": b["fonts"], "footer": b["footer"],
        "lockup": "data:image/png;base64," + base64.b64encode(lockup.read_bytes()).decode(),
    }

    pieces, jobs = {}, []
    for piece in spec["pieces"]:
        pid = str(piece.get("id"))
        lines, problems = check_piece(piece, hooks, brand)
        if pid in pieces:
            problems.append(f"{pid} is in statics.json twice")
        out = folder / "pieces" / pid
        if out.is_dir() and out.parent == folder / "pieces":
            shutil.rmtree(out)          # an old render must never pass for this run's
        pieces[pid] = {"kind": "static", "lines": lines, "problems": problems, "files": {}}
        if problems:
            continue
        hook = next(h for h in hooks["hooks"] if h["id"] == pid.split("-")[0])
        text = {where: t for where, t, _ in lines}
        for size, (w, h) in SIZES.items():
            jobs.append({"id": "Static", "out": str(out / f"{size}.png"), "props": {
                "w": w, "h": h, "safe": safe(size), "brand": look,
                "piece": {
                    "layout": piece["layout"], "chip": "" if hook["customer"] == "all" else hook["customer"],
                    "headline": text["headline"], "support": text.get("support", ""), "label": text.get("label", ""),
                    "cards": [{"title": c.get("title", ""), "rows": [r[:2] for r in c["rows"]]} for c in piece.get("cards", [])],
                    "cta": text["cta"], "url": text["url"],
                }}})

    if jobs:
        (ROOT / "tmp").mkdir(exist_ok=True)
        jobfile = ROOT / "tmp" / f"jobs-{slug}-{batch}.json"
        jobfile.write_text(json.dumps(jobs), encoding="utf-8")
        done = subprocess.run(["node", "render.mjs", str(jobfile)], cwd=RENDER, capture_output=True, text=True, encoding="utf-8", errors="replace")
        failures = [line for line in done.stderr.splitlines() if line.startswith("FAILED")]
        print("\n".join(failures), end="\n" if failures else "")
        if done.returncode and not failures:
            raise BrandError("the renderer stopped: " + (done.stderr.strip().splitlines() or ["no message"])[-1])
    for job in jobs:
        out = Path(job["out"])
        pid, size = out.parent.name, out.stem
        pieces[pid]["problems"] += check_png(out, size, b["colors"]["bg"])
        if out.is_file():
            pieces[pid]["files"][size] = f"pieces/{pid}/{out.name}"

    write_report(folder, slug, batch, "static", pieces)
    failed = {pid: p["problems"] for pid, p in pieces.items() if p["problems"]}
    images = sum(len(p["files"]) for p in pieces.values())
    print(f"{len(pieces) - len(failed)} of {len(pieces)} pieces pass; {images} images in {folder / 'pieces'}")
    for pid, problems in failed.items():
        for p in problems:
            print(f"  FAIL {pid}: {p}")
    return not failed


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m factory.statics <brand> <batch>")
    try:
        sys.exit(0 if run(sys.argv[1], sys.argv[2]) else 1)
    except BrandError as e:
        sys.exit(f"error: {e}")
