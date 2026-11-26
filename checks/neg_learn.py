"""Tests of the learn station beyond the happy path, on a throwaway copy of the real batch
(runs/builtwithbaron/zz-learn-test, made and removed here)."""
import json
import shutil
from factory.brand import ROOT, BrandError
from factory.learn import run

real = ROOT / "runs" / "builtwithbaron" / "2026-11-16-batch1"
test = ROOT / "runs" / "builtwithbaron" / "zz-learn-test"
shutil.rmtree(test, ignore_errors=True)
(test / "results").mkdir(parents=True)
for name in ("gate.json", "hooks.json"):
    shutil.copyfile(real / name, test / name)
shutil.copyfile(real / "results" / "SAMPLE-results.csv", test / "results" / "SAMPLE-results.csv")
HEAD = "piece,platform,date,spend,impressions,views_3s,thruplays,clicks,leads,fit_leads\n"
go = lambda *files: run("builtwithbaron", "zz-learn-test", [str(test / "results" / f) for f in files])


def refused(name, needle, *files):
    try:
        go(*files)
    except BrandError as err:
        ok = needle in str(err)
        print(("ok   " if ok else "MISS ") + f"{name}: {err}")
        assert ok, name
        return
    raise AssertionError(f"{name}: was not refused")


try:
    refused("no real results, only the sample in the folder", "no results yet")
    assert not (test / "scoreboard.md").exists()

    (test / "results" / "week1.csv").write_text(HEAD + "H29-M3-C-video 9x16,meta,2026-12-01,12,2150,710,196,31,2,2\nH01-M3-A,meta,2026-12-01,6,1410,,,9,0,0\n", encoding="utf-8")
    go()
    board = (test / "scoreboard.md").read_text(encoding="utf-8")
    assert "SAMPLE" not in board and "From week1.csv: 2 lines, 2 pieces, 2 hooks" in board and not (test / "SAMPLE-scoreboard.md").exists()
    print("ok   a real file in the folder: scoreboard.md holds only its 2 lines; the sample beside it is left out")

    refused("a sample and a real file named together", "never mixed", "SAMPLE-results.csv", "week1.csv")

    (test / "results" / "relabelled.csv").write_text(HEAD.strip() + ",sample\nH01-M3-A,meta,2026-12-01,6,1410,,,9,0,0,yes\n", encoding="utf-8")
    refused("a sample renamed to look real (its sample column says yes)", "never mixed")
    (test / "results" / "relabelled.csv").unlink()

    (test / "results" / "week1-copy.csv").write_text((test / "results" / "week1.csv").read_text(encoding="utf-8"), encoding="utf-8")
    refused("the same file imported twice", "imported twice")
    (test / "results" / "week1-copy.csv").unlink()

    (test / "results" / "other.csv").write_text(HEAD + "H02-M1-A,meta,2026-12-01,6,1410,,,9,0,0\n", encoding="utf-8")
    refused("a piece that is not in this batch", "H02-M1-A is not in this batch's gate.json")
    (test / "results" / "other.csv").unlink()

    # The review page's export, a rejected piece that ran anyway, a comment made twice, a piece that failed the gate.
    (test / "decisions.json").write_text(json.dumps({"batch": "builtwithbaron:zz-learn-test", "decisions": {
        "H29-M3-C-video": {"decision": "approve", "comment": "Too much text on the end card."},
        "H01-M3-A": {"decision": "reject", "comment": "too much text on the end card"},
        "H14-M4-A": {"decision": "", "comment": ""}}}), encoding="utf-8")
    gate = json.loads((test / "gate.json").read_text(encoding="utf-8"))
    gate["pieces"]["H29-M3-C-video"]["problems"] = ["made to fail for this test"]
    (test / "gate.json").write_text(json.dumps(gate), encoding="utf-8")
    go()
    board = (test / "scoreboard.md").read_text(encoding="utf-8")
    for needle in ("WARNING: H01-M3-A has results although it was rejected on the review page", "WARNING: H29-M3-C-video has results although it failed the gate",
                   "| H01-M3-A | reject | too much text on the end card |", "\"too much text on the end card\" (H29-M3-C-video, H01-M3-A)"):
        assert needle in board, needle
    assert "H14-M4-A" not in board                      # an empty decision is not listed
    print("ok   decisions.json: the rejected piece and the failed piece are warned about, and the comment made twice is listed")

    (test / "decisions.json").write_text(json.dumps({"batch": "builtwithbaron:2026-11-16-batch1", "decisions": {}}), encoding="utf-8")
    refused("a decisions.json exported from another batch", "decisions.json is for")
    print("all learn tests behaved")
finally:
    shutil.rmtree(test, ignore_errors=True)
