"""Negative cases on the real brand and batch: each changed piece must fail the gate."""
import copy
import json

from factory.brand import ROOT, load_brand
from factory.gate import check_piece

brand = load_brand("builtwithbaron")
folder = ROOT / "runs" / "builtwithbaron" / "2026-11-16-batch1"
hooks = json.loads((folder / "hooks.json").read_text(encoding="utf-8"))
base = json.loads((folder / "statics.json").read_text(encoding="utf-8"))["pieces"][0]
assert check_piece(base, hooks, brand)[1] == []

cases = {
    "fact not in facts.md": ["It answers in Spanish too.", "F99"],
    "claim with no fact": ["It books the job.", ""],
    "never-claim (results)": ["Never miss a call again.", "F04"],
    "a price": ["Plans from $99 per month.", "F04"],
    "number not in the fact": ["Set up in 7 days.", "F05"],
    "guarantee": ["30-day money-back guarantee.", "F05"],
    "sounds human": ["Callers can't tell it's AI.", "F06"],
}
for name, support in cases.items():
    p = copy.deepcopy(base)
    p["support"] = support
    problems = check_piece(p, hooks, brand)[1]
    assert problems, name
    print(f"{name:26} -> FAIL: {problems[0]}")
